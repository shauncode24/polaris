from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.inference import ProfileSnapshot
from app.services.github.github_knowledge import build_github_knowledge_object


async def build_leetcode_knowledge_object(db: AsyncSession, user_id) -> dict | None:
    """Aggregates a user's latest LeetCode snapshot data with a high-level
    summary of their GitHub engineering profile. This combined object is
    passed to the LLM to provide holistic coaching comparing algorithmic
    readiness with practical engineering evidence — including whether
    prior coaching advice was actually acted on and whether contest
    rating is trending anywhere.
    """
    # 1. Fetch latest LeetCode snapshot
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

    # 2. Fetch latest GitHub knowledge
    gh_knowledge = await build_github_knowledge_object(db, user_id)

    payload = lc_snapshot.skills_json
    insights = payload.get("insights", {})
    stats = payload.get("stats", {})

    return {
        "leetcode_summary": {
            "total_solved": stats.get("total_solved", 0),
            "easy": stats.get("easy", 0),
            "medium": stats.get("medium", 0),
            "hard": stats.get("hard", 0),
            "contest_rating": stats.get("contest_rating"),
            "active_days_last_30": stats.get("active_days_last_30", 0),
        },
        "topic_mastery": insights.get("topic_mastery", []),
        "blind_spots": insights.get("blind_spots", {}),
        "contest_trajectory": insights.get("contest_trajectory", {}),
        "plan_adherence": insights.get("plan_adherence", []),
        "practice_habits": insights.get("practice_habits", {}),
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
                for r in gh_knowledge.get("repositories", [])
            ] if gh_knowledge else [],
        }
    }