from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Note
from app.models.goals import Goal
from app.models.inference import ProfileSnapshot, SkillEvidence
from app.models.structure import Skill
from app.services.evidence import build_evidence_details
from app.services.resume.confidence import compute_skill_confidence

MAX_PLAN_WEEKS = 16
DEFAULT_PLAN_WEEKS = 8


def compute_weeks_available(deadline: date | None) -> int:
    """Deterministic, not LLM-guessed — same 'code decides facts, LLM only
    reasons over them' rule the rest of the codebase follows
    (effort_estimation.py, confidence.py). Capped at MAX_PLAN_WEEKS so a
    multi-year deadline doesn't produce an unusably long single plan;
    Career Planner v2 (Phase 10) is what re-plans as time actually passes,
    not this basic version.
    """
    if deadline is None:
        return DEFAULT_PLAN_WEEKS
    days_remaining = (deadline - date.today()).days
    weeks = max(1, round(days_remaining / 7))
    return min(weeks, MAX_PLAN_WEEKS)


async def _get_skills_by_confidence(db: AsyncSession) -> list[dict]:
    skill_result = await db.execute(select(Skill))
    skills = skill_result.scalars().all()

    out = []
    for skill in skills:
        evidence_result = await db.execute(
            select(SkillEvidence).where(SkillEvidence.skill_id == skill.id)
        )
        evidence_rows = list(evidence_result.scalars().all())
        if not evidence_rows:
            continue
        confidence = compute_skill_confidence([e.weight for e in evidence_rows])
        details = await build_evidence_details(db, evidence_rows)
        out.append({"skill": skill.canonical_name, "confidence": confidence, "evidence": details})

    out.sort(key=lambda s: s["confidence"])
    return out

async def _get_latest_leetcode_insights(db: AsyncSession, user_id) -> dict:
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note.in_(["leetcode sync", "leetcode manual submission"]))
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None or not isinstance(snapshot.skills_json, dict):
        return {"blind_spots": {"missing_fundamentals": [], "advanced_topics": []}, "topic_mastery": []}

    insights = snapshot.skills_json.get("insights", {})
    return {
        "blind_spots": insights.get("blind_spots", {"missing_fundamentals": [], "advanced_topics": []}),
        "topic_mastery": insights.get("topic_mastery", []),
    }


async def _get_recent_notes(db: AsyncSession, user_id, limit: int = 10) -> list[dict]:
    result = await db.execute(
        select(Note).where(Note.user_id == user_id).order_by(Note.date.desc()).limit(limit)
    )
    return [{"date": n.date.isoformat(), "content": n.content, "tags": n.tags or []} for n in result.scalars().all()]


async def _get_recent_snapshots(db: AsyncSession, user_id, limit: int = 5) -> list[dict]:
    """Deliberately thin at this point in the build — Phase 6 runs before
    Phase 9's timeline view exists. Just enough for the LLM to see that
    *some* history exists, not a full diff (design doc §5.3).
    """
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(limit)
    )
    return [{"taken_at": s.taken_at.isoformat(), "note": s.note} for s in result.scalars().all()]


async def build_career_plan_context(db: AsyncSession, user_id, goal: Goal) -> dict:
    weeks_available = compute_weeks_available(goal.deadline)

    skills_by_confidence = await _get_skills_by_confidence(db)
    leetcode = await _get_latest_leetcode_insights(db, user_id)
    notes = await _get_recent_notes(db, user_id)
    snapshots = await _get_recent_snapshots(db, user_id)

    return {
        "goal": {
            "title": goal.title,
            "deadline": goal.deadline.isoformat() if goal.deadline else None,
            "priority": goal.priority,
        },
        "weeks_available": weeks_available,
        "skills_by_confidence": skills_by_confidence,
        "leetcode_blind_spots": leetcode["blind_spots"],
        "leetcode_topic_mastery": leetcode["topic_mastery"],
        "recent_notes": notes,
        "recent_snapshots": snapshots,
    }