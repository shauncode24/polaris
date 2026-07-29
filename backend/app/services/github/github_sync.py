import asyncio
from collections import defaultdict
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.facts import GithubSnapshot
from app.models.inference import ProfileSnapshot
from app.models.github_analysis import GithubProjectAnalysis
from app.services.github.github_client import (
    GithubSyncError,
    fetch_commit_count_last_30d,
    fetch_ci_config_exists,
    fetch_languages,
    fetch_readme_exists,
    fetch_repos,
    fetch_test_signal,
    fetch_repo_file,
    fetch_repo_path_exists,
    fetch_last_commit_info,
    fetch_recent_commits,
    fetch_pull_request_stats,
    fetch_repo_tree,
    fetch_user_commit_count_capped,
)
from app.services.github.github_insights import build_github_insights, build_repo_headline, build_ranked_recommendations
from app.services.github.github_scoring import score_repository
from app.services.github.github_taxonomy import categorize_technologies
from app.services.github.github_analyzer import analyze_repo
from app.services.github.github_commit_hygiene import score_commit_hygiene
from app.services.github.github_collaboration import score_collaboration
from app.services.github.github_architecture_analyzer import (
    is_eligible_for_architecture_pass,
    assess_architecture_depth,
)
from app.services.github.github_cache import get_repo_cache, cache_is_fresh, upsert_repo_cache


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


def _extract_commit_messages_and_timestamps(recent_commits: list[dict]) -> tuple[list[str], list[datetime]]:
    messages: list[str] = []
    timestamps: list[datetime] = []
    for c in recent_commits:
        commit = c.get("commit") or {}
        message = commit.get("message")
        if message:
            messages.append(message)
        date_str = (commit.get("committer") or {}).get("date") or (commit.get("author") or {}).get("date")
        if date_str:
            try:
                timestamps.append(datetime.fromisoformat(date_str.replace("Z", "+00:00")))
            except ValueError:
                pass
    return messages, timestamps


async def _compute_slow_repo_signals(
    client: httpx.AsyncClient, username: str, repo_name: str, token: str,
    default_branch: str, is_fork: bool, quality_score_hint: float | None,
) -> dict:
    """Runs the four expensive per-repo operations (commit-hygiene sample,
    PR/review lookup, fork-contribution count, architecture LLM pass) from
    scratch. Only ever called on a cache miss — see the branch in
    sync_github() below. `quality_score_hint` is None on a cache miss for
    a repo we haven't analyzed yet this sync, which is fine: the
    architecture eligibility check below runs again with the REAL
    quality_score once analyze_repo() has computed it, so this hint is
    only used to skip an obviously-ineligible tree fetch early when
    available (it isn't, on first pass — kept for future callers).
    """
    recent_commits_task = fetch_recent_commits(client, username, repo_name, token, limit=30)
    pr_stats_task = fetch_pull_request_stats(client, username, repo_name, token)
    fork_contribution_task = (
        fetch_user_commit_count_capped(client, username, repo_name, username, token)
        if is_fork else _immediate(0)
    )

    recent_commits, pr_stats, fork_contribution_commits = await asyncio.gather(
        recent_commits_task, pr_stats_task, fork_contribution_task
    )

    messages, timestamps = _extract_commit_messages_and_timestamps(recent_commits)
    hygiene_result = score_commit_hygiene(messages, timestamps)
    collaboration_result = score_collaboration(
        pr_stats.get("pr_count", 0), pr_stats.get("reviewed_pr_count", 0)
    )

    return {
        "commit_hygiene": hygiene_result,
        "pr_stats": pr_stats,
        "collaboration": collaboration_result,
        "fork_contribution_commits": fork_contribution_commits,
    }


async def _immediate(value):
    """Tiny helper so fork-contribution can share the same asyncio.gather
    call shape whether or not it actually needs to hit the network."""
    return value


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
    cache_hits = cache_misses = 0

    async with httpx.AsyncClient(timeout=20.0) as client:
        repos = await fetch_repos(client, username, token)
        print(f"[TRACING] Found {len(repos)} repos for {username}.", flush=True)

        for repo in repos:
            repo_name = repo["name"]
            is_archived = bool(repo.get("archived", False))
            is_fork = bool(repo.get("fork", False))
            stars = repo.get("stargazers_count", 0)
            forks = repo.get("forks_count", 0)
            topics = repo.get("topics", []) or []
            default_branch = repo.get("default_branch", "main")

            # --- Cheap per-repo calls: always refetched, every sync ---
            languages_task = fetch_languages(client, username, repo_name, token)
            commits_task = fetch_commit_count_last_30d(client, username, repo_name, username, token)
            readme_task = fetch_readme_exists(client, username, repo_name, token)
            ci_task = fetch_ci_config_exists(client, username, repo_name, token)
            tests_task = fetch_test_signal(client, username, repo_name, token, default_branch)
            package_json_task = fetch_repo_file(client, username, repo_name, "package.json", token)
            requirements_task = fetch_repo_file(client, username, repo_name, "requirements.txt", token)
            pyproject_task = fetch_repo_file(client, username, repo_name, "pyproject.toml", token)
            dockerfile_task = fetch_repo_path_exists(client, username, repo_name, "Dockerfile", token)
            compose_yml_task = fetch_repo_path_exists(client, username, repo_name, "docker-compose.yml", token)
            compose_yaml_task = fetch_repo_path_exists(client, username, repo_name, "docker-compose.yaml", token)
            last_commit_info_task = fetch_last_commit_info(client, username, repo_name, token)

            (
                languages,
                commits_30d,
                has_readme,
                has_ci,
                has_tests,
                package_json,
                requirements_txt,
                pyproject_toml,
                has_dockerfile,
                has_compose_yml,
                has_compose_yaml,
                last_commit_info,
            ) = await asyncio.gather(
                languages_task, commits_task, readme_task, ci_task, tests_task,
                package_json_task, requirements_task, pyproject_task,
                dockerfile_task, compose_yml_task, compose_yaml_task,
                last_commit_info_task,
            )

            has_compose = has_compose_yml or has_compose_yaml
            current_sha = last_commit_info["sha"] if last_commit_info else None
            last_commit_at = last_commit_info["date"] if last_commit_info else None

            # --- Cache check: decides whether the 4 slow operations run ---
            cache_row = await get_repo_cache(db, user.id, repo_name)
            if cache_is_fresh(cache_row, current_sha):
                cache_hits += 1
                hygiene_result = cache_row.commit_hygiene
                pr_stats = cache_row.pr_stats
                collaboration_result = cache_row.collaboration
                fork_contribution_commits = cache_row.fork_contribution_commits
                cached_architecture_result = cache_row.architecture_assessment
                print(f"[TRACING] Cache HIT for {repo_name} (sha={current_sha[:8] if current_sha else None})", flush=True)
            else:
                cache_misses += 1
                slow_signals = await _compute_slow_repo_signals(
                    client, username, repo_name, token, default_branch, is_fork, quality_score_hint=None,
                )
                hygiene_result = slow_signals["commit_hygiene"]
                pr_stats = slow_signals["pr_stats"]
                collaboration_result = slow_signals["collaboration"]
                fork_contribution_commits = slow_signals["fork_contribution_commits"]
                cached_architecture_result = None  # computed fresh below, after quality_score exists
                print(f"[TRACING] Cache MISS for {repo_name} (sha={current_sha[:8] if current_sha else None})", flush=True)

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
                is_fork=is_fork, fork_contribution_commits=fork_contribution_commits,
                commit_hygiene_score=hygiene_result["score"],
                collaboration_score=collaboration_result["score"],
            )

            analysis = analyze_repo(
                repo_name=repo_name,
                languages=languages,
                package_json=package_json,
                requirements_txt=requirements_txt,
                pyproject_toml=pyproject_toml,
                has_dockerfile=has_dockerfile,
                has_compose=has_compose,
                has_workflows=has_ci,
                has_tests_dir=has_tests,
                has_readme=has_readme,
                commits_30d=commits_30d,
                last_commit_at=last_commit_at,
                is_archived=is_archived,
                is_fork=is_fork,
                is_meaningful_fork_contribution=score["is_meaningful_fork_contribution"],
            )

            # --- Architecture pass: only run on a cache miss, and only if
            # the repo clears the deterministic bar with its FRESH quality
            # score. On a cache hit, reuse whatever was cached (which may
            # legitimately be None if the repo wasn't eligible last time). ---
            if cache_is_fresh(cache_row, current_sha):
                architecture_result = cached_architecture_result
            elif is_eligible_for_architecture_pass(
                quality_score=analysis["quality_score"],
                is_archived=is_archived,
                is_fork=is_fork,
                contributed_as_fork=score["is_meaningful_fork_contribution"],
            ):
                tree_paths = await fetch_repo_tree(client, username, repo_name, token, default_branch)
                architecture_result = await assess_architecture_depth(
                    repo_name, analysis["technologies"], tree_paths
                )
            else:
                architecture_result = None

            # Persist the cache row for next sync — always written on a
            # miss (even if current_sha is None, e.g. an empty repo,
            # since cache_is_fresh() will simply never match None again
            # and this repo will always take the fresh path, which is
            # correct — nothing to gain by caching an empty repo).
            if not cache_is_fresh(cache_row, current_sha) and current_sha is not None:
                await upsert_repo_cache(
                    db, user_id=user.id, repo_name=repo_name, last_commit_sha=current_sha,
                    commit_hygiene=hygiene_result, pr_stats=pr_stats,
                    collaboration=collaboration_result,
                    fork_contribution_commits=fork_contribution_commits,
                    architecture_assessment=architecture_result,
                )

            repo_entry = {
                "name": repo_name, "stars": stars, "forks": forks,
                "commits_last_30_days": commits_30d,
                "languages": list(languages.keys()),
                "topics": topics, "description": repo.get("description"),
                "pushed_at": repo.get("pushed_at"),
                "archived": is_archived, "is_new": is_new,
                "private": bool(repo.get("private", False)),
                "has_readme": has_readme, "has_ci": has_ci, "has_tests": has_tests,
                "project_score": score,
                "tier": analysis["tier"],
                "is_fork": is_fork,
                "is_meaningful_fork_contribution": score["is_meaningful_fork_contribution"],
                "commit_hygiene": hygiene_result,
                "collaboration": collaboration_result,
                "architecture_assessment": architecture_result,
            }
            repo_entry["headline"] = build_repo_headline({
                **repo_entry,
                "project_score": score,
                "has_readme": has_readme,
                "has_tests": has_tests,
                "has_ci": has_ci
            })
            repositories_report.append(repo_entry)

            insert_vals = {
                "user_id": user.id,
                "repo_name": repo_name,
                "category": analysis["category"],
                "primary_language": analysis["primary_language"],
                "technologies": analysis["technologies"],
                "capabilities": analysis["capabilities"],
                "is_backend": analysis["is_backend"],
                "is_frontend": analysis["is_frontend"],
                "is_database": analysis["is_database"],
                "is_containerized": analysis["is_containerized"],
                "has_readme": analysis["has_readme"],
                "has_tests": analysis["has_tests"],
                "has_ci": analysis["has_ci"],
                "is_active": analysis["is_active"],
                "last_activity_days": analysis["last_activity_days"],
                "activity_score": analysis["activity_score"],
                "quality_score": analysis["quality_score"],
                "maintenance_score": analysis["maintenance_score"],
                "tier": analysis["tier"],
                "is_fork": is_fork,
                "is_meaningful_fork_contribution": score["is_meaningful_fork_contribution"],
                "commit_hygiene_score": hygiene_result["score"],
                "collaboration_mode": collaboration_result["mode"],
                "collaboration_score": collaboration_result["score"],
                "architecture_assessment": architecture_result,
                "computed_at": datetime.now(timezone.utc),
            }

            stmt = (
                pg_insert(GithubProjectAnalysis)
                .values(**insert_vals)
                .on_conflict_do_update(
                    constraint="uq_repo_analysis_user_repo",
                    set_={k: v for k, v in insert_vals.items() if k not in ("id", "user_id", "repo_name")},
                )
            )
            await db.execute(stmt)

    for row in snapshot_rows:
        db.add(row)
    await db.flush()

    print(f"[TRACING] GitHub sync cache: {cache_hits} hits, {cache_misses} misses.", flush=True)

    current_repo_names = {r["name"] for r in repositories_report}
    removed_repo_names = previously_synced - current_repo_names

    if removed_repo_names:
        from sqlalchemy import delete
        await db.execute(
            delete(GithubProjectAnalysis)
            .where(GithubProjectAnalysis.user_id == user.id)
            .where(GithubProjectAnalysis.repo_name.in_(removed_repo_names))
        )

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
    insights["recommendations"] = build_ranked_recommendations(repositories_report)

    summary = {
        "repos_synced": len(repositories_report),
        "new_repositories": new_count,
        "updated_repositories": len(repositories_report) - new_count,
        "archived_repositories": archived_count,
        "removed_repositories": len(removed_repo_names),
        "forked_repositories": sum(1 for r in repositories_report if r["is_fork"]),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "total_commits_last_30_days": total_commits,
        "languages_detected": languages_detected,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
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