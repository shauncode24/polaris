"""Gathers the candidate's ENTIRE real profile as-is — every project,
every experience, every skill with its confidence/evidence, and any
company notes on file — and hands it to the LLM untouched. No scoring,
no filtering, no pre-selection: the model decides what's relevant to a
given question, not this module. The only "decisions" made here are
which tables to query, which is I/O, not judgment.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import CompanyNote, Experience, Project
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.services.evidence import build_evidence_details
from app.services.resume.confidence import compute_skill_confidence


async def _get_all_projects(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(select(Project).where(Project.user_id == user_id))
    return [
        {
            "type": "project",
            "name": p.name,
            "description": p.description or "",
            "stack": p.stack or [],
        }
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
            "bullets": e.bullets or [],
            "stack": e.stack or [],
        }
        for e in result.scalars().all()
    ]


async def _get_all_skills_with_evidence(db: AsyncSession) -> list[dict]:
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


async def _get_company_notes(db: AsyncSession, user_id, target_company: str | None) -> list[dict]:
    if not target_company:
        return []
    result = await db.execute(
        select(CompanyNote)
        .where(CompanyNote.user_id == user_id)
        .where(CompanyNote.company.ilike(target_company))
    )
    return [
        {"company": n.company, "notes": n.pasted_content}
        for n in result.scalars().all()
    ]


async def build_interview_context(
    db: AsyncSession,
    user_id,
    question: str,
    target_role: str | None,
    target_company: str | None,
) -> dict:
    projects = await _get_all_projects(db, user_id)
    experiences = await _get_all_experiences(db, user_id)
    skills = await _get_all_skills_with_evidence(db)
    company_notes = await _get_company_notes(db, user_id, target_company)

    return {
        "question": question,
        "target_role": target_role,
        "target_company": target_company,
        "profile": {
            "projects": projects,
            "experiences": experiences,
            "skills": skills,
        },
        "company_notes": company_notes,
    }