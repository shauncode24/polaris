"""Gathers the candidate's ENTIRE real profile as-is, plus the static
blueprint library and persona config, and hands all of it to the LLM
untouched. No scoring, no filtering, no pre-selection of stories or
blueprints: the model decides what's relevant and which blueprint fits,
not this module.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import CompanyNote, Education, Experience, Project, Resume
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.services.evidence import build_evidence_details
from app.services.interview.blueprints import get_blueprint_library, get_persona
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
    # Get all project IDs and experience IDs for this user to filter evidence
    proj_result = await db.execute(select(Project.id).where(Project.user_id == user_id))
    user_proj_ids = {p[0] for p in proj_result.all()}

    exp_result = await db.execute(select(Experience.id).where(Experience.user_id == user_id))
    user_exp_ids = {e[0] for e in exp_result.all()}

    skill_result = await db.execute(select(Skill))
    skills = skill_result.scalars().all()

    out = []
    for skill in skills:
        evidence_result = await db.execute(select(SkillEvidence).where(SkillEvidence.skill_id == skill.id))
        evidence_rows = list(evidence_result.scalars().all())
        if not evidence_rows:
            continue

        # Keep only evidence rows that belong to this user's projects/experiences
        # or are global/other sources (e.g. leetcode_tag)
        filtered_rows = []
        for e in evidence_rows:
            if e.source_type == "project":
                if e.source_id in user_proj_ids:
                    filtered_rows.append(e)
            elif e.source_type == "experience":
                if e.source_id in user_exp_ids:
                    filtered_rows.append(e)
            else:
                filtered_rows.append(e)

        if not filtered_rows:
            continue

        confidence = compute_decayed_skill_confidence(filtered_rows)
        details = await build_evidence_details(db, filtered_rows)
        out.append({"skill": skill.canonical_name, "confidence": confidence, "evidence": details})

    return out


async def _get_company_notes(db: AsyncSession, user_id, target_company: str | None) -> list[dict]:
    if not target_company:
        return []
    result = await db.execute(
        select(CompanyNote).where(CompanyNote.user_id == user_id).where(CompanyNote.company.ilike(target_company))
    )
    return [{"company": n.company, "notes": n.pasted_content} for n in result.scalars().all()]


async def build_interview_context(
    db: AsyncSession,
    user_id,
    question: str,
    target_role: str | None,
    target_company: str | None,
) -> dict:
    projects = await _get_all_projects(db, user_id)
    experiences = await _get_all_experiences(db, user_id)
    education = await _get_all_education(db, user_id)
    skills = await _get_all_skills_with_evidence(db, user_id)
    github_repos = await _get_github_repo_evidence(db, user_id)
    company_notes = await _get_company_notes(db, user_id, target_company)

    return {
        "question": question,
        "target_role": target_role,
        "target_company": target_company,
        "profile": {
            "projects": projects,
            "experiences": experiences,
            "education": education,
            "skills": skills,
            "github_repos": github_repos,
        },
        "company_notes": company_notes,
        "blueprint_library": get_blueprint_library(),
        "persona": get_persona(),
    }

async def _get_github_repo_evidence(db: AsyncSession, user_id, limit: int = 6) -> list[dict]:
    """Real, verified GitHub repository evidence — commit hygiene,
    collaboration mode, architecture depth — so the Interview Response
    Agent can cite concrete, checkable details (e.g. real PR-review
    collaboration, a "layered" architecture assessment) instead of only
    ever drawing on resume-described projects. Previously this context
    builder never queried GithubProjectAnalysis at all, so questions
    about scalability, collaboration, or code quality had nothing real
    from GitHub to cite even when strong evidence existed.

    Non-contributed forks are excluded — same rule applied everywhere
    else GitHub evidence is surfaced (github_knowledge.py, coverage.py).
    Ranked by quality+activity and capped so the prompt payload stays
    small, same approach as github_knowledge.py.
    """
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