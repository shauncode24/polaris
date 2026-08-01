"""Explicit GitHub-repo linking for projects.

This is the deterministic fix for the Projects module's weakest failure
mode: overview.py used to join Project -> GithubProjectAnalysis with a
silent `p.name.lower() == repo_name.lower()` runtime guess. A mismatch
(e.g. resume project "Cortex Route" vs repo "cortex-route-gateway")
dropped all GitHub-derived scoring/tier/technology enrichment with no
error and nothing visible to the user.

The fix: `Project.github_repo_name` is an explicit, persisted link.
Nothing in this module ever writes that column silently — a candidate
link is only ever a *suggestion* (returned by suggest_repo_links) until
a user confirms it via link_project(). Only an exact normalized-name
match is safe enough to prefer as the default suggestion; fuzzy matches
still require confirmation, same as the design doc's "user confirming
ambiguous matches" requirement.
"""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Project, Resume
from app.models.github_analysis import GithubProjectAnalysis

_PREFIX_RE = re.compile(r"^project\s*\d+\s*[:\-\s]\s*", re.IGNORECASE)
_PAREN_RE = re.compile(r"\s*\([^)]*\)")
_BRACKET_RE = re.compile(r"\s*\[[^\]]*\]")
_NORMALIZE_RE = re.compile(r"[^a-z0-9]")


def normalize_name(name: str) -> str:
    # Remove "Project 1:", "Project 2 -", etc.
    cleaned = _PREFIX_RE.sub("", name)
    # Remove "(Ongoing)", "(Live Link)", etc.
    cleaned = _PAREN_RE.sub("", cleaned)
    cleaned = _BRACKET_RE.sub("", cleaned)
    return _NORMALIZE_RE.sub("", cleaned.lower())


async def suggest_repo_links(db: AsyncSession, user_id) -> list[dict]:
    """Returns one suggestion per unlinked project:
    {"project_id", "project_name", "candidate_repo", "confidence", "other_candidates"}
    confidence is "exact" | "fuzzy" | "none". Never mutates the database.
    """
    proj_result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id, Project.github_repo_name.is_(None))
        .order_by(Project.created_at.desc())
    )
    all_unlinked = list(proj_result.scalars().all())

    # De-duplicate by normalized project name, keeping the most recent one
    seen_names = set()
    unlinked = []
    for p in all_unlinked:
        norm = normalize_name(p.name)
        if norm not in seen_names:
            seen_names.add(norm)
            unlinked.append(p)

    if not unlinked:
        return []

    repo_result = await db.execute(
        select(GithubProjectAnalysis.repo_name).where(GithubProjectAnalysis.user_id == user_id)
    )
    repo_names = [r[0] for r in repo_result.all()]
    from app.services.projects.repo_linking import match_project_to_repo

    suggestions = []
    for project in unlinked:
        norm_project = normalize_name(project.name)
        matched = match_project_to_repo(project.name, project.repo_url, repo_names)

        if matched and normalize_name(matched) == norm_project:
            suggestions.append({
                "project_id": str(project.id),
                "project_name": project.name,
                "candidate_repo": matched,
                "confidence": "exact",
                "other_candidates": [],
            })
        elif matched:
            others = [
                r for r in repo_names
                if r != matched and norm_project and (norm_project in normalize_name(r) or normalize_name(r) in norm_project)
            ]
            suggestions.append({
                "project_id": str(project.id),
                "project_name": project.name,
                "candidate_repo": matched,
                "confidence": "fuzzy",
                "other_candidates": others[:3],
            })
        else:
            suggestions.append({
                "project_id": str(project.id),
                "project_name": project.name,
                "candidate_repo": None,
                "confidence": "none",
                "other_candidates": [],
            })

    return suggestions


async def link_project(db: AsyncSession, user_id, project_id, repo_name: str) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        return None
    project.github_repo_name = repo_name
    project.repo_link_status = "confirmed"
    await db.commit()
    await db.refresh(project)
    return project


async def unlink_project(db: AsyncSession, user_id, project_id) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        return None
    project.github_repo_name = None
    project.repo_link_status = "unmatched"
    await db.commit()
    await db.refresh(project)
    return project