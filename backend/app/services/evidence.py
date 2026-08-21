from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Experience, Project
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.services.resume.confidence import compute_decayed_skill_confidence


async def build_evidence_details(db: AsyncSession, evidence_rows: list[SkillEvidence]) -> list[str]:
    """Human-readable evidence trail for a list of SkillEvidence rows.
    Unchanged by the user-scoping fix — it operates on rows already
    handed to it by a caller, and never queries SkillEvidence itself.

    Phase 4: added a "linkedin_profile" branch so LinkedIn-sourced
    evidence gets a real, visible provenance label instead of silently
    contributing to confidence math with no corresponding detail string
    (previously the only source_type that fell through every branch).
    """
    project_ids = [e.source_id for e in evidence_rows if e.source_type == "project" and e.source_id]
    experience_ids = [e.source_id for e in evidence_rows if e.source_type == "experience" and e.source_id]
    github_repo_ids = [e.source_id for e in evidence_rows if e.source_type == "github_repo" and e.source_id]

    projects: dict = {}
    if project_ids:
        result = await db.execute(select(Project).where(Project.id.in_(project_ids)))
        projects = {p.id: p for p in result.scalars().all()}

    experiences: dict = {}
    if experience_ids:
        result = await db.execute(select(Experience).where(Experience.id.in_(experience_ids)))
        experiences = {e.id: e for e in result.scalars().all()}

    github_repos: dict = {}
    if github_repo_ids:
        result = await db.execute(
            select(GithubProjectAnalysis).where(GithubProjectAnalysis.id.in_(github_repo_ids))
        )
        github_repos = {r.id: r for r in result.scalars().all()}

    details: list[str] = []
    for e in evidence_rows:
        if e.source_type == "project" and e.source_id in projects:
            details.append(f"Project: {projects[e.source_id].name}")
        elif e.source_type == "experience" and e.source_id in experiences:
            exp = experiences[e.source_id]
            details.append(f"Experience: {exp.role} at {exp.company}")
        elif e.source_type == "github_repo" and e.source_id in github_repos:
            details.append(f"GitHub: {github_repos[e.source_id].repo_name}")
        elif e.source_type == "leetcode_tag":
            details.append("LeetCode practice history")
        elif e.source_type == "certificate":
            details.append("Certificate")
        elif e.source_type == "linkedin_profile":
            details.append("LinkedIn profile")
    return list(dict.fromkeys(details))


async def get_all_skill_confidences(db: AsyncSession, user_id) -> dict[str, float]:
    """canonical_name -> recency-decayed confidence, for ONE user.

    FIX (cross-user evidence leak): `user_id` is now a REQUIRED parameter
    with no default.
    """
    result = await db.execute(select(Skill))
    skills = result.scalars().all()
    out: dict[str, float] = {}
    for skill in skills:
        ev = await db.execute(
            select(SkillEvidence).where(
                SkillEvidence.skill_id == skill.id,
                SkillEvidence.user_id == user_id,
            )
        )
        rows = list(ev.scalars().all())
        if rows:
            out[skill.canonical_name] = compute_decayed_skill_confidence(rows)
    return out