from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inference import ProfileSnapshot
from app.services.github.github_knowledge import build_github_knowledge_object
from app.services.leetcode.engineering_snapshot import compute_engineering_snapshot


async def build_leetcode_knowledge_object(
    db: AsyncSession,
    user_id,
    github_knowledge: dict | None = None,
    engineering_snapshot: dict | None = None,
) -> dict | None:
    """Aggregates a user's latest LeetCode snapshot data with a high-level
    summary of their GitHub engineering profile, for the on-demand AI
    Coach review call.

    `github_knowledge` / `engineering_snapshot` can be passed in by a
    caller that has ALREADY computed them this request (Engineering
    Identity fix #6 — identity_builder.py used to trigger this function,
    which independently re-fetched github_knowledge AND recomputed
    compute_engineering_snapshot, duplicating work identity_builder had
    already done itself). When omitted (e.g. leetcode_reviewer.py's
    standalone call), this computes them fresh exactly as before.
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

    if github_knowledge is None:
        github_knowledge = await build_github_knowledge_object(db, user_id)
    gh_knowledge = github_knowledge

    payload = lc_snapshot.skills_json
    insights = payload.get("insights", {})
    stats = payload.get("stats", {})
    topic_mastery = insights.get("topic_mastery", [])
    repositories = gh_knowledge.get("repositories", []) if gh_knowledge else []

    if engineering_snapshot is None:
        engineering_snapshot = await compute_engineering_snapshot(db, user_id)
    engineering = engineering_snapshot

    return {
        "leetcode_summary": {
            "total_solved": stats.get("total_solved", 0),
            "easy": stats.get("easy", 0),
            "medium": stats.get("medium", 0),
            "hard": stats.get("hard", 0),
            "contest_rating": stats.get("contest_rating"),
            "active_days_last_30": stats.get("active_days_last_30", 0),
        },
        "topic_mastery": topic_mastery,
        "blind_spots": insights.get("blind_spots", {}),
        "contest_trajectory": insights.get("contest_trajectory", {}),
        "plan_adherence": insights.get("plan_adherence", []),
        "practice_habits": insights.get("practice_habits", {}),
        "practice_diversity": insights.get("practice_diversity", {}),
        "data_ceiling_note": insights.get("data_ceiling_note", ""),
        "difficulty_insight": insights.get("difficulty_insight", ""),
        "engineering_quadrant": (
            {
                "leetcode_score": engineering["leetcode_score"],
                "github_score": engineering["github_score"],
                "quadrant_label": engineering["quadrant_label"],
                "description": engineering["description"],
            }
            if engineering else None
        ),
        "company_readiness": engineering["company_readiness"] if engineering else [],
        "resume_claims": engineering["resume_claims"] if engineering else {},
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