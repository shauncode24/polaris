from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Experience, Project
from app.models.inference import SkillEvidence


async def build_evidence_details(db: AsyncSession, evidence_rows: list[SkillEvidence]) -> list[str]:
    """Human-readable evidence trail for a list of SkillEvidence rows —
    joins back to Project/Experience since SkillEvidence itself only
    stores a weight + source_id. Shared by Skill Gap Analyzer (Phase 4)
    and Career Planner (Phase 6) so both agents describe the same
    evidence the same way, instead of duplicating this join logic.
    """
    project_ids = [e.source_id for e in evidence_rows if e.source_type == "project" and e.source_id]
    experience_ids = [e.source_id for e in evidence_rows if e.source_type == "experience" and e.source_id]

    projects: dict = {}
    if project_ids:
        result = await db.execute(select(Project).where(Project.id.in_(project_ids)))
        projects = {p.id: p for p in result.scalars().all()}

    experiences: dict = {}
    if experience_ids:
        result = await db.execute(select(Experience).where(Experience.id.in_(experience_ids)))
        experiences = {e.id: e for e in result.scalars().all()}

    details: list[str] = []
    for e in evidence_rows:
        if e.source_type == "project" and e.source_id in projects:
            details.append(f"Project: {projects[e.source_id].name}")
        elif e.source_type == "experience" and e.source_id in experiences:
            exp = experiences[e.source_id]
            details.append(f"Experience: {exp.role} at {exp.company}")
        elif e.source_type == "leetcode_tag":
            details.append("LeetCode practice history")
        elif e.source_type == "certificate":
            details.append("Certificate")
    return list(dict.fromkeys(details))