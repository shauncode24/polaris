from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Experience, Project
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.services.resume.confidence import compute_decayed_skill_confidence


async def build_evidence_details(db: AsyncSession, evidence_rows: list[SkillEvidence]) -> list[str]:
    """Human-readable evidence trail for a list of SkillEvidence rows —
    joins back to Project/Experience/GithubProjectAnalysis since
    SkillEvidence itself only stores a weight + source_id. Shared by
    Skill Gap Analyzer, Career Planner, and the Interview Response Agent
    so every surface describes the same evidence the same way, instead
    of duplicating this join logic.
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
    return list(dict.fromkeys(details))


async def get_all_skill_confidences(db: AsyncSession) -> dict[str, float]:
    """canonical_name -> recency-decayed confidence, for every skill with
    at least one evidence row — resume, GitHub, LeetCode, and certificate
    evidence all summed and decay-weighted together (see
    resume/confidence.py and resume/decay.py). This is the single
    unified evidence pool: bullet-strength scoring, narrative coherence,
    tailoring, and role-fit (role_fit.py) all read from here instead of
    each recomputing their own partial view of "what does this person
    actually know."
    """
    result = await db.execute(select(Skill))
    skills = result.scalars().all()
    out: dict[str, float] = {}
    for skill in skills:
        ev = await db.execute(select(SkillEvidence).where(SkillEvidence.skill_id == skill.id))
        rows = list(ev.scalars().all())
        if rows:
            out[skill.canonical_name] = compute_decayed_skill_confidence(rows)
    return out