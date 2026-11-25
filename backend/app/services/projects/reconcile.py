"""Keeps a user's projects in line with their synced GitHub repos.

One idempotent function, safe to run after a GitHub sync, a resume upload
or a link change:

1. Exact matches are linked automatically. A resume project that has no
   repo link, was not rejected by the user, and either points at a synced
   repo by URL or has the same normalised name as one gets linked
   (link status "auto", source "both"). Fuzzy matches are NOT linked: they
   stay suggestions for the user to confirm (see linking.suggest_repo_links).

2. Every synced repo that no resume project links becomes a project of its
   own (source "github"), so work that never made it onto the resume is
   still part of the user's evidence. Forks count only when the user made a
   meaningful contribution to them.

3. When a resume project does link a repo, the GitHub-only project for that
   repo is merged away, unless the user has reviewed it (confirmed, edited
   or hidden it) - the user's decisions are never destroyed.

4. A GitHub-only project whose repo is gone from GitHub is removed, again
   unless the user has reviewed it.

Rows the user has taken ownership of (review_state other than "auto") are
never overwritten here.
"""
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Project
from app.models.github_analysis import GithubProjectAnalysis
from app.services.projects.linking import normalize_name
from app.services.projects.repo_linking import repo_name_from_url

logger = logging.getLogger(__name__)

RESUME_SOURCES = ("resume", "both")


@dataclass
class ReconcileResult:
    auto_linked: int = 0
    created: int = 0
    updated: int = 0
    merged: int = 0
    removed: int = 0

    @property
    def changed(self) -> bool:
        return any((self.auto_linked, self.created, self.updated, self.merged, self.removed))


def _is_eligible(analysis: GithubProjectAnalysis) -> bool:
    return not analysis.is_fork or bool(analysis.is_meaningful_fork_contribution)


def _exact_repo_match(project: Project, repo_names_by_slug: dict[str, str]) -> str | None:
    """The repo this project unambiguously refers to, or None. Deliberately
    stricter than repo_linking.match_project_to_repo: no substring matching.
    """
    url_repo = repo_name_from_url(project.repo_url)
    if url_repo:
        match = repo_names_by_slug.get(normalize_name(url_repo))
        if match:
            return match
    return repo_names_by_slug.get(normalize_name(project.name))


async def reconcile_projects(db: AsyncSession, user_id) -> ReconcileResult:
    result = ReconcileResult()

    analyses = list(
        (await db.execute(select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)))
        .scalars().all()
    )
    analysis_by_repo = {a.repo_name: a for a in analyses}
    repo_names_by_slug = {normalize_name(a.repo_name): a.repo_name for a in analyses if normalize_name(a.repo_name)}

    projects = list((await db.execute(select(Project).where(Project.user_id == user_id))).scalars().all())
    resume_projects = [p for p in projects if p.source in RESUME_SOURCES]
    github_projects = {p.github_repo_name: p for p in projects if p.source == "github"}

    # 1. Link exact matches.
    for project in resume_projects:
        if project.github_repo_name or project.repo_link_status == "rejected":
            continue
        match = _exact_repo_match(project, repo_names_by_slug)
        if match:
            project.github_repo_name = match
            project.repo_link_status = "auto"
            project.source = "both"
            result.auto_linked += 1

    linked_repos = {p.github_repo_name for p in resume_projects if p.github_repo_name}

    # 2-4. One GitHub-sourced project per unlinked, eligible repo.
    for repo_name, analysis in analysis_by_repo.items():
        existing = github_projects.get(repo_name)

        if repo_name in linked_repos:
            if existing is not None and existing.review_state == "auto":
                await db.delete(existing)
                result.merged += 1
            continue

        if not _is_eligible(analysis):
            continue

        if existing is None:
            db.add(Project(
                user_id=user_id, resume_id=None, name=analysis.repo_name,
                description=analysis.description, stack=list(analysis.technologies or []),
                repo_url=analysis.html_url, github_repo_name=analysis.repo_name,
                repo_link_status="auto", source="github",
            ))
            result.created += 1
        elif existing.review_state == "auto":
            new_values = {
                "description": analysis.description,
                "stack": list(analysis.technologies or []),
                "repo_url": analysis.html_url,
            }
            if any(getattr(existing, field) != value for field, value in new_values.items()):
                for field, value in new_values.items():
                    setattr(existing, field, value)
                result.updated += 1

    for repo_name, existing in github_projects.items():
        if repo_name not in analysis_by_repo and existing.review_state == "auto":
            await db.delete(existing)
            result.removed += 1

    await db.commit()
    if result.changed:
        logger.info("Reconciled projects for user %s: %s", user_id, result)
    return result
