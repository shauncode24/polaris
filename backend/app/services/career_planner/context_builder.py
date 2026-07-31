from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import JobDescription, Note, Project, Resume
from app.models.goals import Goal
from app.services.projects.linking import normalize_name
from app.models.inference import ProfileSnapshot, ResumeReview, SkillEvidence
from app.models.structure import Skill
from app.services.evidence import build_evidence_details
from app.services.career_planner.curriculum import get_curriculum_topics, get_relevant_domains
from app.services.career_planner.topic_signals import build_topic_signals
from app.services.resume.confidence import compute_skill_confidence

MAX_PLAN_DAYS = 14
DEFAULT_PLAN_DAYS = 5
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


async def _get_job_description_context(db: AsyncSession, user_id, job_description_id) -> dict | None:
    """Full JD + gap-analysis context for the SPECIFIC job this goal was
    created from, so the planner grounds itself in that job's actual
    role/company and actual missing skills — not whichever JD happens to
    be most recently analyzed for this user. Falls back to the user's
    most recent analyzed JD only for goals that weren't tied to one
    (e.g. manually-entered goals with no "Analyzed job" selection).
    """
    if job_description_id is not None:
        result = await db.execute(
            select(JobDescription)
            .where(JobDescription.id == job_description_id)
            .where(JobDescription.user_id == user_id)
        )
    else:
        result = await db.execute(
            select(JobDescription)
            .where(JobDescription.user_id == user_id)
            .where(JobDescription.analysis_result.isnot(None))
            .order_by(JobDescription.created_at.desc())
            .limit(1)
        )
    jd = result.scalar_one_or_none()
    if jd is None or not isinstance(jd.analysis_result, dict):
        return None

    report = jd.analysis_result.get("report", {})
    overall = jd.analysis_result.get("overall_match", {})
    extracted = jd.extracted_requirements or {}

    return {
        "role": jd.role,
        "company": jd.company,
        "required_skills": extracted.get("raw_required", []),
        "implicit_skills": extracted.get("raw_implicit", []),
        "architecture_topics": extracted.get("architecture_topics", []),
        "nice_to_have": extracted.get("raw_nice_to_have", []),
        "overall_match_percentage": overall.get("percentage"),
        "overall_match_label": overall.get("label"),
        "missing_skills": [
            {"skill": m.get("skill"), "reason": m.get("reason"), "estimated_weeks": m.get("estimated_weeks")}
            for m in report.get("missing", [])
        ],
        "have_skills": [h.get("skill") for h in report.get("have", [])],
        "partial_skills": [p.get("skill") for p in report.get("partial", [])],
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
    all_p = result.scalars().all()
    seen = set()
    projects = []
    for p in all_p:
        norm = normalize_name(p.name)
        if norm not in seen:
            seen.add(norm)
            projects.append({"name": p.name, "description": p.description, "stack": p.stack or []})
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
        return {"blind_spots": {"missing_fundamentals": [], "advanced_topics": []}, "topic_mastery": []}

    insights = snapshot.skills_json.get("insights", {})
    return {
        "blind_spots": insights.get("blind_spots", {"missing_fundamentals": [], "advanced_topics": []}),
        "topic_mastery": insights.get("topic_mastery", []),
    }


async def _get_github_technology_depth(db: AsyncSession, user_id) -> dict[str, dict] | None:
    """Loads the technology_depth map from the latest GitHub sync snapshot.
    Returns None if no sync has happened yet (career planner gracefully
    treats None as no GitHub evidence).
    """
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

    skills_by_confidence = await _get_skills_by_confidence(db)
    target_job = await _get_job_description_context(db, user_id, goal.job_description_id)
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
        # The scoped curriculum pool — ADVISORY. Coverage/order are hints,
        # not instructions. The LLM decides real priority and sequencing.
        "target_job": target_job,
        "topic_signals": topic_signals,
        "resume_review_top_fixes": resume_top_fixes,
        # Kept for grounding cross-cutting tasks (e.g. "use your existing
        # FastAPI experience to serve the model you build this week") —
        # NOT used to pick which topics are in scope. That's curriculum's job.
        "profile_skills_summary": [
            {"skill": s["skill"], "confidence": s["confidence"]} for s in skills_by_confidence
        ],
        "projects": projects,
        "leetcode_blind_spots": leetcode["blind_spots"],
        "leetcode_topic_mastery": leetcode["topic_mastery"],
        "recent_notes": notes,
        "recent_snapshots": snapshots,
    }