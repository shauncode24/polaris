from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import JobDescription, Note, Project
from app.models.goals import Goal
from app.models.inference import ProfileSnapshot, ResumeReview, SkillEvidence
from app.models.structure import Skill
from app.services.evidence import build_evidence_details
from app.services.career_planner.priority_scoring import build_skill_signals
from app.services.resume.confidence import compute_skill_confidence

MAX_PLAN_DAYS = 14
DEFAULT_PLAN_DAYS = 5
MAX_SIGNALS_IN_PROMPT = 10
MAX_PROJECTS_IN_PROMPT = 6


def compute_days_available(deadline: date | None) -> int:
    if deadline is None:
        return DEFAULT_PLAN_DAYS
    days_remaining = (deadline - date.today()).days
    return max(1, min(days_remaining, MAX_PLAN_DAYS))


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

    return out


async def _get_previous_skill_confidence(db: AsyncSession, user_id) -> dict[str, float]:
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note == "resume upload")
        .order_by(ProfileSnapshot.taken_at.desc())
        .offset(1)
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None or not isinstance(snapshot.skills_json, dict):
        return {}
    return {
        canonical: data.get("confidence", 0.0)
        for canonical, data in snapshot.skills_json.items()
        if isinstance(data, dict)
    }


async def _get_latest_jd_missing_skills(db: AsyncSession, user_id) -> set[str]:
    result = await db.execute(
        select(JobDescription.analysis_result)
        .where(JobDescription.user_id == user_id)
        .where(JobDescription.analysis_result.isnot(None))
        .order_by(JobDescription.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return set()
    missing = (row.get("report") or {}).get("missing", [])
    return {m["skill"] for m in missing if isinstance(m, dict) and "skill" in m}


async def _get_latest_ats_flags(db: AsyncSession, user_id) -> tuple[set[str], list[str]]:
    """Pulls the most recent Resume Review (Phase 5) so the planner can
    tie tasks back to real ATS/resume weaknesses instead of the two
    agents never talking to each other.
    Returns (missing_keyword_like_skill_names, raw_top_priority_fixes).
    We can't reliably map every ATS flag to a canonical skill name, so we
    surface the raw top_priority_fixes text too — the LLM can use those
    directly even when they don't resolve to a known skill.
    """
    result = await db.execute(
        select(ResumeReview)
        .where(ResumeReview.user_id == user_id)
        .order_by(ResumeReview.created_at.desc())
        .limit(1)
    )
    review = result.scalar_one_or_none()
    if review is None or not isinstance(review.review_json, dict):
        return set(), []

    top_fixes = review.review_json.get("top_priority_fixes", [])
    ats_flags = review.review_json.get("ats_flags", [])
    # Best-effort: treat any single-word-ish detail in an ATS flag as a
    # possible skill name (e.g. "Missing keyword: Docker") — loose on
    # purpose, this only feeds an advisory signal, never a hard filter.
    keyword_guesses = set()
    for flag in ats_flags:
        detail = flag.get("detail", "") if isinstance(flag, dict) else ""
        for word in detail.replace(":", " ").split():
            cleaned = word.strip(".,").lower()
            if len(cleaned) > 2:
                keyword_guesses.add(cleaned)

    return keyword_guesses, top_fixes


async def _get_projects(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(
        select(Project).where(Project.user_id == user_id).limit(MAX_PROJECTS_IN_PROMPT)
    )
    return [
        {"name": p.name, "description": p.description, "stack": p.stack or []}
        for p in result.scalars().all()
    ]


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


async def _get_recent_notes(db: AsyncSession, user_id, limit: int = 5) -> list[dict]:
    result = await db.execute(
        select(Note).where(Note.user_id == user_id).order_by(Note.date.desc()).limit(limit)
    )
    return [{"date": n.date.isoformat(), "content": n.content, "tags": n.tags or []} for n in result.scalars().all()]


async def _get_recent_snapshots(db: AsyncSession, user_id, limit: int = 3) -> list[dict]:
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(limit)
    )
    return [{"taken_at": s.taken_at.isoformat(), "note": s.note} for s in result.scalars().all()]


async def build_career_plan_context(db: AsyncSession, user_id, goal: Goal) -> dict:
    days_available = compute_days_available(goal.deadline)

    skills_by_confidence = await _get_skills_by_confidence(db)
    previous_confidence = await _get_previous_skill_confidence(db, user_id)
    jd_missing_skills = await _get_latest_jd_missing_skills(db, user_id)
    ats_missing_keywords, resume_top_fixes = await _get_latest_ats_flags(db, user_id)

    skill_signals = build_skill_signals(
        skills_by_confidence,
        goal_title=goal.title,
        jd_missing_skills=jd_missing_skills,
        ats_missing_keywords=ats_missing_keywords,
        previous_skill_confidence=previous_confidence,
    )[:MAX_SIGNALS_IN_PROMPT]

    projects = await _get_projects(db, user_id)
    leetcode = await _get_latest_leetcode_insights(db, user_id)
    notes = await _get_recent_notes(db, user_id)
    snapshots = await _get_recent_snapshots(db, user_id)

    return {
        "goal": {
            "title": goal.title,
            "deadline": goal.deadline.isoformat() if goal.deadline else None,
            "priority": goal.priority,
        },
        "days_available": days_available,
        # ADVISORY ONLY — a rough starting point, not a rulebook.
        "skill_signals": skill_signals,
        "resume_review_top_fixes": resume_top_fixes,
        "projects": projects,
        "leetcode_blind_spots": leetcode["blind_spots"],
        "leetcode_topic_mastery": leetcode["topic_mastery"],
        "recent_notes": notes,
        "recent_snapshots": snapshots,
    }