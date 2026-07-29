"""SHA-gated cache access for the expensive per-repo sync computations.
See GithubRepoAnalysisCache's docstring for why SHA, not a TTL: a repo
whose HEAD hasn't moved since the last sync cannot have a different
commit history, PR history, or file tree, so cached results are never
stale as long as the SHA still matches — no expiry window to tune.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_analysis import GithubRepoAnalysisCache


async def get_repo_cache(db: AsyncSession, user_id, repo_name: str) -> GithubRepoAnalysisCache | None:
    result = await db.execute(
        select(GithubRepoAnalysisCache)
        .where(GithubRepoAnalysisCache.user_id == user_id)
        .where(GithubRepoAnalysisCache.repo_name == repo_name)
    )
    return result.scalar_one_or_none()


def cache_is_fresh(cache_row: GithubRepoAnalysisCache | None, current_sha: str | None) -> bool:
    """False whenever current_sha is unknown (e.g. an empty repo with no
    commits) — an unknown SHA can never be safely matched against a cache
    entry, so those repos always take the fresh-computation path.
    """
    if cache_row is None or current_sha is None:
        return False
    return cache_row.last_commit_sha == current_sha


async def upsert_repo_cache(
    db: AsyncSession,
    *,
    user_id,
    repo_name: str,
    last_commit_sha: str,
    commit_hygiene: dict,
    pr_stats: dict,
    collaboration: dict,
    fork_contribution_commits: int,
    architecture_assessment: dict | None,
) -> None:
    values = {
        "user_id": user_id,
        "repo_name": repo_name,
        "last_commit_sha": last_commit_sha,
        "commit_hygiene": commit_hygiene,
        "pr_stats": pr_stats,
        "collaboration": collaboration,
        "fork_contribution_commits": fork_contribution_commits,
        "architecture_assessment": architecture_assessment,
        "computed_at": datetime.now(timezone.utc),
    }
    stmt = (
        pg_insert(GithubRepoAnalysisCache)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_repo_cache_user_repo",
            set_={k: v for k, v in values.items() if k not in ("user_id", "repo_name")},
        )
    )
    await db.execute(stmt)