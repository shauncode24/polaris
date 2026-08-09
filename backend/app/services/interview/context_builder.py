"""Gathers the candidate's ENTIRE real profile as-is, plus the static
blueprint library and persona config, and hands all of it to the LLM
untouched. No scoring, no filtering, no pre-selection of stories or
blueprints: the model decides what's relevant and which blueprint fits,
not this module.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import CompanyNote, Education, Experience, Project, Resume
from app.models.inference import ProfileSnapshot, SkillEvidence, ProjectClaimAuditReview
from app.models.structure import Skill
from app.services.evidence import build_evidence_details
from app.services.interview.blueprints import get_blueprint_library, get_persona
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.resume.confidence import compute_decayed_skill_confidence


from app.services.projects.linking import normalize_name

from app.models.github_analysis import GithubProjectAnalysis

async def _get_all_projects(db: AsyncSession, user_id) -> list[dict]:
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
            projects.append({"type": "project", "name": p.name, "description": p.description or "", "stack": p.stack or []})
    return projects


async def _get_all_experiences(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(
        select(Experience)
        .where(Experience.user_id == user_id)
        .order_by(Experience.start_date.desc().nullsfirst(), Experience.created_at.desc())
    )
    all_e = result.scalars().all()
    seen = set()
    experiences = []
    for e in all_e:
        key = f"{normalize_name(e.role)}@{normalize_name(e.company)}"
        if key not in seen:
            seen.add(key)
            experiences.append({
                "type": "experience",
                "label": f"{e.role} at {e.company}",
                "role": e.role,
                "company": e.company,
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "end_date": e.end_date.isoformat() if e.end_date else None,
                "bullets": e.bullets or [],
                "stack": e.stack or [],
            })
    return experiences


async def _get_all_education(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(
        select(Education)
        .where(Education.user_id == user_id)
        .order_by(Education.end_date.desc().nullsfirst(), Education.created_at.desc())
    )
    all_edu = result.scalars().all()
    seen = set()
    education = []
    for e in all_edu:
        key = f"{normalize_name(e.institution)}@{normalize_name(e.degree or '')}"
        if key not in seen:
            seen.add(key)
            education.append({
                "type": "education",
                "institution": e.institution,
                "degree": e.degree,
                "field_of_study": e.field_of_study,
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "end_date": e.end_date.isoformat() if e.end_date else None,
                "is_current": e.is_current,
                "details": e.details or [],
            })
    return education


async def _get_all_skills_with_evidence(db: AsyncSession, user_id) -> list[dict]:
    skill_result = await db.execute(select(Skill))
    skills = skill_result.scalars().all()

    out = []
    for skill in skills:
        evidence_result = await db.execute(
            select(SkillEvidence).where(
                SkillEvidence.skill_id == skill.id,
                SkillEvidence.user_id == user_id,
            )
        )
        evidence_rows = list(evidence_result.scalars().all())
        if not evidence_rows:
            continue

        confidence = compute_decayed_skill_confidence(evidence_rows)
        details = await build_evidence_details(db, evidence_rows)
        out.append({"skill": skill.canonical_name, "confidence": confidence, "evidence": details})

    return out


async def _get_company_notes(db: AsyncSession, user_id, target_company: str | None) -> list[dict]:
    if not target_company:
        return []
    result = await db.execute(
        select(CompanyNote).where(CompanyNote.user_id == user_id).where(CompanyNote.company.ilike(target_company))
    )
    return [{"company": n.company, "notes": n.pasted_content} for n in result.scalars().all()]


async def _get_leetcode_evidence(db: AsyncSession, user_id) -> dict | None:
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note.in_(["leetcode sync", "leetcode manual submission"]))
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None or not isinstance(snapshot.skills_json, dict):
        return None

    stats = snapshot.skills_json.get("stats", {})
    insights = snapshot.skills_json.get("insights", {})
    topic_mastery = insights.get("topic_mastery", [])

    mastery_order = {
        "Extensive Practice": 0, "Consistent Practice": 1,
        "Some Practice": 2, "Introduced": 3, "Not Practiced": 4,
    }
    top_topics = sorted(
        [t for t in topic_mastery if t["problems"] > 0],
        key=lambda t: (mastery_order.get(t["mastery"], 5), -t["problems"]),
    )[:5]

    return {
        "total_solved": stats.get("total_solved", 0),
        "easy": stats.get("easy", 0),
        "medium": stats.get("medium", 0),
        "hard": stats.get("hard", 0),
        "top_topics": [{"topic": t["topic"], "mastery": t["mastery"], "problems": t["problems"]} for t in top_topics],
        "blind_spots": insights.get("blind_spots", {}).get("missing_fundamentals", []),
    }


async def _get_project_claim_flags(db: AsyncSession, user_id) -> list[dict]:
    proj_result = await db.execute(select(Project.id, Project.name).where(Project.user_id == user_id))
    projects_by_id = {pid: name for pid, name in proj_result.all()}
    if not projects_by_id:
        return []

    audit_result = await db.execute(
        select(ProjectClaimAuditReview).where(ProjectClaimAuditReview.project_id.in_(projects_by_id.keys()))
    )
    flags = []
    for row in audit_result.scalars().all():
        narrative = (row.report_json or {}).get("narrative", {})
        if narrative.get("risk_level") in ("high", "medium"):
            flags.append({
                "project": projects_by_id.get(row.project_id, "Unknown project"),
                "risk_level": narrative.get("risk_level"),
                "headline": narrative.get("headline", ""),
            })
    return flags


async def _get_target_job_intelligence(db: AsyncSession, job_intelligence_id: str | None) -> dict | None:
    """NEW — optional grounding in a real, deterministic Job Intelligence
    profile (design doc §6.2). Returns a slim projection, not the whole
    profile: only the fields the interview prompt can actually act on
    (seniority calibration, real interview_focus_areas, required
    technologies) — never the raw enriched-skill/category plumbing that
    has no narrative use here.
    """
    if not job_intelligence_id:
        return None
    profile = await get_job_intelligence(db, UUID(job_intelligence_id))
    if profile is None:
        return None
    return {
        "role": profile.role,
        "company": profile.company,
        "seniority_signal": profile.seniority_signal.model_dump(),
        "interview_focus_areas": profile.interview_focus_areas,
        "required_technologies": profile.all_required_technologies,
    }


async def build_interview_context(
    db: AsyncSession,
    user_id,
    question: str,
    target_role: str | None,
    target_company: str | None,
    job_intelligence_id: str | None = None,
) -> dict:
    projects = await _get_all_projects(db, user_id)
    experiences = await _get_all_experiences(db, user_id)
    education = await _get_all_education(db, user_id)
    skills = await _get_all_skills_with_evidence(db, user_id)
    github_repos = await _get_github_repo_evidence(db, user_id)
    leetcode_evidence = await _get_leetcode_evidence(db, user_id)
    company_notes = await _get_company_notes(db, user_id, target_company)
    target_job_intelligence = await _get_target_job_intelligence(db, job_intelligence_id)

    return {
        "question": question,
        "target_role": target_role,
        "target_company": target_company,
        "target_job_intelligence": target_job_intelligence,
        "profile": {
            "projects": projects,
            "experiences": experiences,
            "education": education,
            "skills": skills,
            "github_repos": github_repos,
            "leetcode_evidence": leetcode_evidence,
            "project_claim_flags": await _get_project_claim_flags(db, user_id),
        },
        "company_notes": company_notes,
        "blueprint_library": get_blueprint_library(),
        "persona": get_persona(),
    }

async def _get_github_repo_evidence(db: AsyncSession, user_id, limit: int = 6) -> list[dict]:
    result = await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)
    )
    eligible = [
        a for a in result.scalars().all()
        if not (a.is_fork and not a.is_meaningful_fork_contribution)
    ]
    ranked = sorted(eligible, key=lambda a: a.quality_score * 0.6 + a.activity_score * 0.4, reverse=True)

    return [
        {
            "type": "github_repo",
            "name": a.repo_name,
            "category": a.category,
            "technologies": a.technologies,
            "capabilities": a.capabilities,
            "tier": a.tier,
            "quality_score": a.quality_score,
            "activity_score": a.activity_score,
            "has_tests": a.has_tests,
            "has_ci": a.has_ci,
            "commit_hygiene_score": a.commit_hygiene_score,
            "collaboration_mode": a.collaboration_mode,
            "architecture_depth": (a.architecture_assessment or {}).get("depth_label"),
        }
        for a in ranked[:limit]
    ]