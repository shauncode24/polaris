from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Note, Project, Resume
from app.models.goals import Goal
from app.services.projects.linking import normalize_name
from app.models.inference import ProfileSnapshot, ResumeReview
from app.services.career_planner.curriculum import get_curriculum_topics, get_relevant_domains
from app.services.career_planner.topic_signals import build_topic_signals
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.job_intelligence.gap_results import get_latest_gap_result, is_current_gap_result
from app.services.job_intelligence.library import get_primary_job_id
from app.services.skill_gap.category_breakdown import compute_overall_match
from app.services.skill_gap.comparison import load_evidence_view, match_requirements
from app.services.skill_gap.effort_estimation import estimate_weeks
from app.services.taxonomy.skill_taxonomy import get_curriculum_rank
from app.services.evidence.confidence import get_reconciled_skill_confidences
from app.services.evidence.review import dedupe_visible

MAX_PLAN_DAYS = 14
DEFAULT_PLAN_DAYS = 5
MAX_PROJECTS_IN_PROMPT = 6
_SEVERITY_ORDER = {"critical": 0, "moderate": 1, "minor": 2}


def compute_days_available(deadline: date | None) -> int:
    if deadline is None:
        return DEFAULT_PLAN_DAYS
    days_remaining = (deadline - date.today()).days
    return max(1, min(days_remaining, MAX_PLAN_DAYS))


async def _get_skills_by_confidence(db: AsyncSession, user_id) -> list[dict]:
    """Phase 3 alignment fix: now delegates to the shared, unbounded
    reconciled-confidence map (get_reconciled_skill_confidences) so the
    Career Planner sees the same claim-risk / timeline-discounted
    confidence values as Engineering Identity and the Skill Gap Analyzer.

    Previously this re-derived confidence directly from SkillEvidence
    using compute_decayed_skill_confidence — missing the claim-risk and
    timeline-plausibility discounting that reconciled_confidence applies.
    This was the last place in the codebase with an independent confidence
    derivation.

    Return shape preserved: [{"skill": str, "confidence": float, "evidence": list[str]}]
    so build_topic_signals() and profile_skills_summary work unchanged.
    """
    reconciled = await get_reconciled_skill_confidences(db, user_id)
    return [
        {
            "skill": entry["skill"],
            "confidence": entry["confidence"],
            "evidence": entry.get("sources", []),
        }
        for entry in reconciled.values()
    ]


async def _target_job_id(db: AsyncSession, user_id, job_intelligence_id):
    """The goal's own job; otherwise the user's primary target; otherwise
    the job they compared most recently.
    """
    if job_intelligence_id is not None:
        return job_intelligence_id
    primary_id = await get_primary_job_id(db, user_id)
    if primary_id is not None:
        return primary_id
    latest = await get_latest_gap_result(db, user_id)
    return latest.job_intelligence_id if latest is not None else None


async def _match_for_job(db: AsyncSession, user_id, job_intelligence) -> tuple[dict, dict]:
    """(report, overall match) for the job against the user's evidence now.
    The stored comparison is used while it is current, because it carries the
    effort estimates; otherwise the match is worked out afresh.
    """
    stored = await get_latest_gap_result(db, user_id, UUID(job_intelligence.id))
    if stored is not None and await is_current_gap_result(db, user_id, stored):
        return stored.report_json or {}, stored.overall_match_json or {}

    requirements = job_intelligence.canonical_skills_map
    if not requirements:
        return {}, {}
    view = await load_evidence_view(db, user_id, set(requirements))
    have, partial, missing = match_requirements(requirements, view)
    for entry in missing:
        entry.estimated_weeks = estimate_weeks(1)
    missing.sort(key=lambda m: (_SEVERITY_ORDER[m.severity], get_curriculum_rank(m.skill)))
    report = {
        group: [entry.model_dump(mode="json") for entry in entries]
        for group, entries in (("have", have), ("partial", partial), ("missing", missing))
    }
    return report, compute_overall_match(requirements, have, partial, missing)


async def _get_target_job_context(db: AsyncSession, user_id, job_intelligence_id) -> dict | None:
    """Role facts plus the current match for the job this plan is for (see
    `_target_job_id`). Returns None when the user has no such job.
    """
    job_id = await _target_job_id(db, user_id, job_intelligence_id)
    if job_id is None:
        return None
    job_intelligence = await get_job_intelligence(db, user_id, job_id)
    if job_intelligence is None:
        return None

    report, overall = await _match_for_job(db, user_id, job_intelligence)
    return {
        "role": job_intelligence.role,
        "company": job_intelligence.company,
        "required_skills": [s.raw for s in job_intelligence.enriched_required_skills],
        "implicit_skills": [s.raw for s in job_intelligence.enriched_implicit_skills],
        "architecture_topics": job_intelligence.architecture_topics,
        "nice_to_have": [s.raw for s in job_intelligence.enriched_nice_to_have],
        "overall_match_percentage": overall.get("percentage"),
        "overall_match_label": overall.get("label"),
        "missing_skills": [
            {"skill": m.get("skill"), "reason": m.get("reason"), "estimated_weeks": m.get("estimated_weeks")}
            for m in report.get("missing", [])
        ],
        "have_skills": [h.get("skill") for h in report.get("have", [])],
        "partial_skills": [p.get("skill") for p in report.get("partial", [])],
        "seniority_signal": job_intelligence.seniority_signal.model_dump(),
        "interview_focus_areas": job_intelligence.interview_focus_areas,
    }


async def _get_latest_ats_flags(db: AsyncSession, user_id) -> tuple[set[str], list[str]]:
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
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
    )
    projects = [
        {"name": p.name, "description": p.description, "stack": p.stack or []}
        for p in dedupe_visible("projects", list(result.scalars().all()))
    ]
    return projects[:MAX_PROJECTS_IN_PROMPT]


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
        return {
            "blind_spots": {"missing_fundamentals": [], "advanced_topics": []},
            "topic_mastery": [],
            "plan_adherence": [],
        }

    insights = snapshot.skills_json.get("insights", {})
    return {
        "blind_spots": insights.get("blind_spots", {"missing_fundamentals": [], "advanced_topics": []}),
        "topic_mastery": insights.get("topic_mastery", []),
        "plan_adherence": insights.get("plan_adherence", []),
    }


async def _get_github_technology_depth(db: AsyncSession, user_id) -> dict[str, dict] | None:
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note == "github sync")
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None or not isinstance(snapshot.skills_json, dict):
        return None
    insights = snapshot.skills_json.get("insights", {})
    depth = insights.get("technology_depth")
    return depth if isinstance(depth, dict) else None


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

    relevant_domains = get_relevant_domains(goal.title)
    curriculum_topics = get_curriculum_topics(relevant_domains)

    skills_by_confidence = await _get_skills_by_confidence(db, user_id)
    target_job = await _get_target_job_context(db, user_id, goal.job_intelligence_id)
    jd_missing_skills = {m["skill"] for m in (target_job["missing_skills"] if target_job else []) if m.get("skill")}
    ats_missing_keywords, resume_top_fixes = await _get_latest_ats_flags(db, user_id)
    leetcode = await _get_latest_leetcode_insights(db, user_id)

    topic_signals = build_topic_signals(
        curriculum_topics,
        skills_by_confidence=skills_by_confidence,
        leetcode_topic_mastery=leetcode["topic_mastery"],
        jd_missing_skills=jd_missing_skills,
        ats_missing_keywords=ats_missing_keywords,
        technology_depth=await _get_github_technology_depth(db, user_id),
    )

    projects = await _get_projects(db, user_id)
    notes = await _get_recent_notes(db, user_id)
    snapshots = await _get_recent_snapshots(db, user_id)

    return {
        "goal": {
            "title": goal.title,
            "deadline": goal.deadline.isoformat() if goal.deadline else None,
            "priority": goal.priority,
        },
        "days_available": days_available,
        "relevant_domains": relevant_domains,
        "target_job": target_job,
        "topic_signals": topic_signals,
        "resume_review_top_fixes": resume_top_fixes,
        "profile_skills_summary": [
            {"skill": s["skill"], "confidence": s["confidence"]} for s in skills_by_confidence
        ],
        "projects": projects,
        "leetcode_blind_spots": leetcode["blind_spots"],
        "leetcode_topic_mastery": leetcode["topic_mastery"],
        "leetcode_plan_adherence": leetcode["plan_adherence"],
        "recent_notes": notes,
        "recent_snapshots": snapshots,
    }