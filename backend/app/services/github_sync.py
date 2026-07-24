# backend/app/services/github_sync.py
from collections import defaultdict
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import GithubSnapshot
from app.models.inference import ProfileSnapshot
from app.models.github_analysis import GithubProjectAnalysis, PortfolioAnalysis
from app.services.github_analyzer import analyze_repo, build_portfolio_analysis
from app.services.github_client import (
    GithubSyncError,
    fetch_commit_count_last_30d,
    fetch_languages,
    fetch_last_commit_date,
    fetch_repo_file,
    fetch_repo_path_exists,
    fetch_repos,
)
from app.services.user_helpers import get_or_create_default_user


async def _get_previously_synced_repo_names(db: AsyncSession, user_id) -> set[str]:
    result = await db.execute(
        select(GithubSnapshot.repo_name).where(GithubSnapshot.user_id == user_id).distinct()
    )
    return {row[0] for row in result.all()}


def _aggregate_languages(repo_language_map: dict[str, dict]) -> list[dict]:
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


async def _get_previous_technology_distribution(db: AsyncSession, user_id) -> dict[str, int] | None:
    """Most recent portfolio_analysis row's tech distribution, used to
    compute 'X usage increased since last sync' observations. None on a
    user's very first sync, since there's nothing to diff against yet.
    """
    result = await db.execute(
        select(PortfolioAnalysis.technology_distribution)
        .where(PortfolioAnalysis.user_id == user_id)
        .order_by(PortfolioAnalysis.computed_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row


async def _inspect_repo(
    client: httpx.AsyncClient, owner: str, repo_name: str, token: str
) -> dict:
    """One place that fetches everything the analyzer needs about a single
    repo's contents. Isolated here so sync_github's main loop stays
    readable, and so this is the one spot to touch if you add more
    manifest types later (e.g. go.mod, Cargo.toml).
    """
    package_json = await fetch_repo_file(client, owner, repo_name, "package.json", token)
    requirements_txt = await fetch_repo_file(client, owner, repo_name, "requirements.txt", token)
    pyproject_toml = await fetch_repo_file(client, owner, repo_name, "pyproject.toml", token)
    has_dockerfile = await fetch_repo_path_exists(client, owner, repo_name, "Dockerfile", token)
    has_compose = await fetch_repo_path_exists(client, owner, repo_name, "docker-compose.yml", token)
    has_workflows = await fetch_repo_path_exists(client, owner, repo_name, ".github/workflows", token)
    has_tests_dir = (
        await fetch_repo_path_exists(client, owner, repo_name, "tests", token)
        or await fetch_repo_path_exists(client, owner, repo_name, "test", token)
    )
    has_readme = await fetch_repo_path_exists(client, owner, repo_name, "README.md", token)
    last_commit_at = await fetch_last_commit_date(client, owner, repo_name, token)

    return {
        "package_json": package_json,
        "requirements_txt": requirements_txt,
        "pyproject_toml": pyproject_toml,
        "has_dockerfile": has_dockerfile,
        "has_compose": has_compose,
        "has_workflows": has_workflows,
        "has_tests_dir": has_tests_dir,
        "has_readme": has_readme,
        "last_commit_at": last_commit_at,
    }


async def _upsert_repo_analysis(db: AsyncSession, user_id, analysis: dict, computed_at: datetime) -> None:
    stmt = (
        pg_insert(GithubProjectAnalysis)
        .values(
            user_id=user_id,
            computed_at=computed_at,
            **analysis,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "repo_name"],
            set_={**analysis, "computed_at": computed_at},
        )
    )
    await db.execute(stmt)


async def sync_github(db: AsyncSession, username: str, token: str) -> dict:
    if not username or not token:
        raise GithubSyncError("GITHUB_USERNAME and GITHUB_TOKEN must both be set")

    print(f"[TRACING] Starting GitHub sync for {username}...", flush=True)
    user = await get_or_create_default_user(db)
    previously_synced = await _get_previously_synced_repo_names(db, user.id)
    previous_tech_distribution = await _get_previous_technology_distribution(db, user.id)

    repo_language_map: dict[str, dict] = {}
    repositories_report: list[dict] = []
    repo_analyses: list[dict] = []
    snapshot_rows: list[GithubSnapshot] = []

    total_stars = total_forks = total_commits = 0
    new_count = archived_count = 0

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
            inspection = await _inspect_repo(client, username, repo_name, token)

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
                    user_id=user.id, pulled_at=datetime.now(timezone.utc),
                    repo_name=repo_name, commits_30d=commits_30d,
                    languages=languages, stars=stars,
                )
            )
            repositories_report.append({
                "name": repo_name, "stars": stars, "forks": forks,
                "commits_last_30_days": commits_30d, "languages": list(languages.keys()),
                "archived": is_archived, "is_new": is_new,
            })

            analysis = analyze_repo(
                repo_name=repo_name, languages=languages,
                package_json=inspection["package_json"],
                requirements_txt=inspection["requirements_txt"],
                pyproject_toml=inspection["pyproject_toml"],
                has_dockerfile=inspection["has_dockerfile"],
                has_compose=inspection["has_compose"],
                has_workflows=inspection["has_workflows"],
                has_tests_dir=inspection["has_tests_dir"],
                has_readme=inspection["has_readme"],
                commits_30d=commits_30d,
                last_commit_at=inspection["last_commit_at"],
                is_archived=is_archived,
            )
            repo_analyses.append(analysis)

    for row in snapshot_rows:
        db.add(row)
    await db.flush()

    computed_at = datetime.now(timezone.utc)
    for analysis in repo_analyses:
        await _upsert_repo_analysis(db, user.id, analysis, computed_at)

    current_repo_names = {r["name"] for r in repositories_report}
    removed_repo_names = previously_synced - current_repo_names
    languages_detected = _aggregate_languages(repo_language_map)

    snapshot = ProfileSnapshot(
        user_id=user.id, taken_at=computed_at,
        skills_json={"repos_synced": sorted(current_repo_names)}, note="github sync",
    )
    db.add(snapshot)
    await db.flush()

    portfolio = build_portfolio_analysis(repo_analyses, previous_tech_distribution)
    db.add(PortfolioAnalysis(
        user_id=user.id, snapshot_id=snapshot.id, computed_at=computed_at, **portfolio,
    ))
    await db.flush()
    await db.commit()

    print(f"[TRACING] GitHub sync complete. {len(snapshot_rows)} repo snapshots + analysis written.", flush=True)

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
        "insights": portfolio,   # <-- this is the new part: Interview Agent /
                                 #     Career Planner / Resume Reviewer can all
                                 #     read this directly instead of re-parsing GitHub
    }