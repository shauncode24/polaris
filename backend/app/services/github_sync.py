from collections import defaultdict
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import GithubSnapshot
from app.models.inference import ProfileSnapshot
from app.services.github_client import (
    GithubSyncError,
    fetch_commit_count_last_30d,
    fetch_languages,
    fetch_repos,
)
from app.services.user_helpers import get_or_create_default_user


async def _get_previously_synced_repo_names(db: AsyncSession, user_id) -> set[str]:
    """Repo names seen in any prior GitHub sync for this user — used to
    tell 'new' repos apart from 'updated' ones, and to notice repos that
    have disappeared (renamed/deleted) since the last sync.
    """
    result = await db.execute(
        select(GithubSnapshot.repo_name).where(GithubSnapshot.user_id == user_id).distinct()
    )
    return {row[0] for row in result.all()}


def _aggregate_languages(repo_language_map: dict[str, dict]) -> list[dict]:
    """repo_language_map: {repo_name: {language: bytes, ...}, ...}
    Returns [{"language": ..., "repos": n, "bytes": n}], sorted by bytes desc.
    """
    totals: dict[str, int] = defaultdict(int)
    repo_counts: dict[str, int] = defaultdict(int)
    for languages in repo_language_map.values():
        for lang, byte_count in languages.items():
            totals[lang] += byte_count
            repo_counts[lang] += 1

    return [
        {"language": lang, "repos": repo_counts[lang], "bytes": totals[lang]}
        for lang in sorted(totals, key=lambda l: totals[l], reverse=True)
    ]


async def sync_github(db: AsyncSession, username: str, token: str) -> dict:
    if not username or not token:
        raise GithubSyncError("GITHUB_USERNAME and GITHUB_TOKEN must both be set")

    print(f"[TRACING] Starting GitHub sync for {username}...", flush=True)
    user = await get_or_create_default_user(db)

    # Snapshot the "before" state so we can report what actually changed,
    # not just what the account currently looks like.
    previously_synced = await _get_previously_synced_repo_names(db, user.id)

    repo_language_map: dict[str, dict] = {}
    repositories_report: list[dict] = []
    snapshot_rows: list[GithubSnapshot] = []

    total_stars = 0
    total_forks = 0
    total_commits = 0
    new_count = 0
    archived_count = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        repos = await fetch_repos(client, username, token)
        print(f"[TRACING] Found {len(repos)} repos for {username}.", flush=True)

        for repo in repos:
            repo_name = repo["name"]
            is_archived = bool(repo.get("archived", False))
            stars = repo.get("stargazers_count", 0)
            forks = repo.get("forks_count", 0)

            languages = await fetch_languages(client, username, repo_name, token)
            commits_30d = await fetch_commit_count_last_30d(client, username, repo_name, username, token)

            repo_language_map[repo_name] = languages
            is_new = repo_name not in previously_synced

            if is_new:
                new_count += 1
            if is_archived:
                archived_count += 1

            total_stars += stars
            total_forks += forks
            total_commits += commits_30d

            snapshot_rows.append(
                GithubSnapshot(
                    user_id=user.id,
                    pulled_at=datetime.now(timezone.utc),
                    repo_name=repo_name,
                    commits_30d=commits_30d,
                    languages=languages,
                    stars=stars,
                )
            )

            repositories_report.append(
                {
                    "name": repo_name,
                    "stars": stars,
                    "forks": forks,
                    "commits_last_30_days": commits_30d,
                    "languages": list(languages.keys()),
                    "archived": is_archived,
                    "is_new": is_new,
                }
            )

    for row in snapshot_rows:
        db.add(row)
    await db.flush()

    current_repo_names = {r["name"] for r in repositories_report}
    removed_repo_names = previously_synced - current_repo_names
    languages_detected = _aggregate_languages(repo_language_map)

    snapshot = ProfileSnapshot(
        user_id=user.id,
        taken_at=datetime.now(timezone.utc),
        skills_json={"repos_synced": sorted(current_repo_names)},
        note="github sync",
    )
    db.add(snapshot)
    await db.flush()
    await db.commit()

    print(f"[TRACING] GitHub sync complete. {len(snapshot_rows)} repo snapshots written.", flush=True)

    return {
        "status": "success",
        "synced_at": snapshot.taken_at.isoformat(),
        "user_id": str(user.id),
        "snapshot_id": str(snapshot.id),
        "summary": {
            "repos_synced": len(repositories_report),
            "new_repositories": new_count,
            "updated_repositories": len(repositories_report) - new_count,
            "archived_repositories": archived_count,
            "removed_repositories": len(removed_repo_names),
            "total_stars": total_stars,
            "total_forks": total_forks,
            "total_commits_last_30_days": total_commits,
            "languages_detected": languages_detected,
        },
        "repositories": repositories_report,
        "removed_repository_names": sorted(removed_repo_names),
        "profile_snapshot_created": True,
    }