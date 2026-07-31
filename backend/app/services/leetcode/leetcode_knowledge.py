from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inference import ProfileSnapshot
from app.models.facts import Resume
from app.services.github.github_knowledge import build_github_knowledge_object
from app.services.leetcode.engineering_quadrant import compute_engineering_quadrant
from app.services.leetcode.company_readiness import compute_company_readiness
from app.services.leetcode.resume_claim_check import check_resume_claims


async def _get_latest_resume_text(db: AsyncSession, user_id) -> str:
    result = await db.execute(
        select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(1)
    )
    resume = result.scalar_one_or_none()
    return resume.raw_text if resume else ""


async def build_leetcode_knowledge_object(db: AsyncSession, user_id) -> dict | None:
    """Aggregates a user's latest LeetCode snapshot data with a high-level
    summary of their GitHub engineering profile. This combined object is
    passed to the LLM to provide holistic coaching comparing algorithmic
    readiness with practical engineering evidence — including whether
    prior coaching advice was actually acted on, whether contest rating
    is trending anywhere, the cross-module Engineering Maturity Quadrant,
    company-specific readiness, and resume-claim verification.
    """
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note.in_(["leetcode sync", "leetcode manual submission"]))
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    lc_snapshot = result.scalar_one_or_none()
    if lc_snapshot is None or not isinstance(lc_snapshot.skills_json, dict):
        return None

    gh_knowledge = await build_github_knowledge_object(db, user_id)

    payload = lc_snapshot.skills_json
    insights = payload.get("insights", {})
    stats = payload.get("stats", {})
    topic_mastery = insights.get("topic_mastery", [])
    repositories = gh_knowledge.get("repositories", []) if gh_knowledge else []

    # New cross-module inferences (LeetCode Module Review §5) — all
    # deterministic; only their narration is left to the LLM.
    engineering_quadrant = compute_engineering_quadrant(topic_mastery, repositories)
    company_readiness = compute_company_readiness(topic_mastery)

    resume_text = await _get_latest_resume_text(db, user_id)
    resume_claims = check_resume_claims(
        resume_text,
        total_solved=stats.get("total_solved", 0),
        contest_rating=stats.get("contest_rating"),
        topic_mastery=topic_mastery,
    )

    return {
        "leetcode_summary": {
            "total_solved": stats.get("total_solved", 0),
            "easy": stats.get("easy", 0),
            "medium": stats.get("medium", 0),
            "hard": stats.get("hard", 0),
            "contest_rating": stats.get("contest_rating"),
            "active_days_last_30": stats.get("active_days_last_30", 0),
            # global_ranking deliberately omitted from the LLM-facing
            # summary — demoted per §3, not a career-actionable headline stat.
        },
        "topic_mastery": topic_mastery,
        "blind_spots": insights.get("blind_spots", {}),
        "contest_trajectory": insights.get("contest_trajectory", {}),
        "plan_adherence": insights.get("plan_adherence", []),
        "practice_habits": insights.get("practice_habits", {}),
        "practice_diversity": insights.get("practice_diversity", {}),
        "data_ceiling_note": insights.get("data_ceiling_note", ""),
        "difficulty_insight": insights.get("difficulty_insight", ""),
        "engineering_quadrant": engineering_quadrant,
        "company_readiness": company_readiness,
        "resume_claims": resume_claims,
        "github_summary": {
            "all_technologies": gh_knowledge.get("all_technologies", []) if gh_knowledge else [],
            "all_capabilities": gh_knowledge.get("all_capabilities", []) if gh_knowledge else [],
            "repositories": [
                {
                    "name": r["name"],
                    "category": r.get("category"),
                    "tier": r.get("tier"),
                    "quality_score": r.get("quality_score"),
                    "activity_score": r.get("activity_score"),
                }
                for r in repositories
            ],
        },
    }