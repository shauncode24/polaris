from collections import defaultdict
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import GithubSnapshot
from app.models.inference import ProfileSnapshot
from app.services.github.github_client import (
    GithubSyncError,
    fetch_commit_count_last_30d,
    fetch_ci_config_exists,
    fetch_languages,
    fetch_readme_exists,
    fetch_repos,
    fetch_test_signal,
)
from app.services.github.github_insights import build_github_insights
from app.services.github.github_scoring import score_repository
from app.services.github.github_taxonomy import categorize_technologies


async def _get_previously_synced_repo_names(db: AsyncSession, user_id) -> set[str]:
    result = await db.execute(
        select(GithubSnapshot.repo_name).where(GithubSnapshot.user_id == user_id).distinct()
    )
    return {row[0] for row in result.all()}


def _aggregate_languages(repo_language_map: dict[str, dict]) -> tuple[list[dict], dict[str, int]]:
    totals: dict[str, int] = defaultdict(int)
    repo_counts: dict[str, int] = defaultdict(int)
    for languages in repo_language_map.values():
        for lang, byte_count in languages.items():
            totals[lang] += byte_count
            repo_counts[lang] += 1

    detected = [
        {"language": lang, "repos": repo_counts[lang], "bytes": totals[lang]}
        for lang in sorted(totals, key=lambda l: totals[l], reverse=True)
    ]
    return detected, dict(totals)


async def sync_github(db: AsyncSession, user, username: str, token: str) -> dict:
    if not username or not token:
        raise GithubSyncError("GitHub username and token must both be provided")

    print(f"[TRACING] Starting GitHub sync for {username}...", flush=True)
    previously_synced = await _get_previously_synced_repo_names(db, user.id)

    repo_language_map: dict[str, dict] = {}
    repo_topics_map: dict[str, list[str]] = {}
    repositories_report: list[dict] = []
    snapshot_rows: list[GithubSnapshot] = []

    total_stars = total_forks = total_commits = new_count = archived_count = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        repos = await fetch_repos(client, username, token)
        print(f"[TRACING] Found {len(repos)} repos for {username}.", flush=True)

        for repo in repos:
            repo_name = repo["name"]
            is_archived = bool(repo.get("archived", False))
            stars = repo.get("stargazers_count", 0)
            forks = repo.get("forks_count", 0)
            topics = repo.get("topics", []) or []
            default_branch = repo.get("default_branch", "main")

            languages = await fetch_languages(client, username, repo_name, token)
            commits_30d = await fetch_commit_count_last_30d(client, username, repo_name, username, token)
            has_readme = await fetch_readme_exists(client, username, repo_name, token)
            has_ci = await fetch_ci_config_exists(client, username, repo_name, token)
            has_tests = await fetch_test_signal(client, username, repo_name, token, default_branch)

            repo_language_map[repo_name] = languages
            repo_topics_map[repo_name] = topics
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
                    user_id=user.id, pulled_at=datetime.now(timezone.utc),
                    repo_name=repo_name, commits_30d=commits_30d,
                    languages=languages, stars=stars,
                )
            )

            score = score_repository(
                commits_30d=commits_30d, stars=stars, forks=forks,
                has_readme=has_readme, has_ci=has_ci, has_tests=has_tests,
                size_kb=repo.get("size", 0), language_count=len(languages),
                topic_count=len(topics), pushed_at=repo.get("pushed_at"),
                archived=is_archived, has_description=bool(repo.get("description")),
            )

            repositories_report.append({
                "name": repo_name, "stars": stars, "forks": forks,
                "commits_last_30_days": commits_30d,
                "languages": list(languages.keys()),
                "topics": topics, "description": repo.get("description"),
                "pushed_at": repo.get("pushed_at"),
                "archived": is_archived, "is_new": is_new,
                "private": bool(repo.get("private", False)),
                "has_readme": has_readme, "has_ci": has_ci, "has_tests": has_tests,
                "project_score": score,
            })

    for row in snapshot_rows:
        db.add(row)
    await db.flush()

    current_repo_names = {r["name"] for r in repositories_report}
    removed_repo_names = previously_synced - current_repo_names
    languages_detected, total_language_bytes = _aggregate_languages(repo_language_map)
    tech_distribution = categorize_technologies(repo_language_map, repo_topics_map)
    scores = {r["name"]: r["project_score"]["overall"] for r in repositories_report}

    prev_stmt = (
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user.id)
        .where(ProfileSnapshot.note == "github sync")
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    prev_result = await db.execute(prev_stmt)
    prev_snapshot = prev_result.scalar_one_or_none()
    prev_insights = None
    if prev_snapshot and isinstance(prev_snapshot.skills_json, dict):
        prev_insights = prev_snapshot.skills_json.get("insights")

    insights = build_github_insights(
        repositories_report, scores, tech_distribution, total_language_bytes, prev_insights
    )

    summary = {
        "repos_synced": len(repositories_report),
        "new_repositories": new_count,
        "updated_repositories": len(repositories_report) - new_count,
        "archived_repositories": archived_count,
        "removed_repositories": len(removed_repo_names),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "total_commits_last_30_days": total_commits,
        "languages_detected": languages_detected,
    }

    snapshot = ProfileSnapshot(
        user_id=user.id, taken_at=datetime.now(timezone.utc),
        skills_json={
            "username": username,
            "repos_synced": sorted(current_repo_names),
            "repositories": repositories_report,
            "summary": summary,
            "insights": insights,
        },
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
        "username": username,
        "summary": summary,
        "repositories": repositories_report,
        "removed_repository_names": sorted(removed_repo_names),
        "insights": insights,
        "profile_snapshot_created": True,
    }