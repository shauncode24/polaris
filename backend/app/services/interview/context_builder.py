"""Gathers the candidate's ENTIRE real profile as-is, plus the static
blueprint library and persona config, and hands all of it to the LLM
untouched. No scoring, no filtering, no pre-selection of stories or
blueprints: the model decides what's relevant and which blueprint fits,
not this module.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import CompanyNote, Education, Experience, Project
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.services.evidence import build_evidence_details
from app.services.interview.blueprints import get_blueprint_library, get_persona
from app.services.resume.confidence import compute_skill_confidence


async def _get_all_projects(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(select(Project).where(Project.user_id == user_id))
    return [
        {"type": "project", "name": p.name, "description": p.description or "", "stack": p.stack or []}
        for p in result.scalars().all()
    ]


async def _get_all_experiences(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(select(Experience).where(Experience.user_id == user_id))
    return [
        {
            "type": "experience",
            "label": f"{e.role} at {e.company}",
            "role": e.role,
            "company": e.company,
            "start_date": e.start_date.isoformat() if e.start_date else None,
            "end_date": e.end_date.isoformat() if e.end_date else None,
            "bullets": e.bullets or [],
            "stack": e.stack or [],
        }
        for e in result.scalars().all()
    ]


async def _get_all_education(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(select(Education).where(Education.user_id == user_id))
    return [
        {
            "type": "education",
            "institution": e.institution,
            "degree": e.degree,
            "field_of_study": e.field_of_study,
            "start_date": e.start_date.isoformat() if e.start_date else None,
            "end_date": e.end_date.isoformat() if e.end_date else None,
            "is_current": e.is_current,
            "details": e.details or [],
        }
        for e in result.scalars().all()
    ]


async def _get_all_skills_with_evidence(db: AsyncSession) -> list[dict]:
    skill_result = await db.execute(select(Skill))
    skills = skill_result.scalars().all()

    out = []
    for skill in skills:
        evidence_result = await db.execute(select(SkillEvidence).where(SkillEvidence.skill_id == skill.id))
        evidence_rows = list(evidence_result.scalars().all())
        if not evidence_rows:
            continue
        confidence = compute_skill_confidence([e.weight for e in evidence_rows])
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
    skills = await _get_all_skills_with_evidence(db)
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
        },
        "company_notes": company_notes,
        "blueprint_library": get_blueprint_library(),
        "persona": get_persona(),
    }