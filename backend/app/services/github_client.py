from datetime import datetime, timedelta, timezone

import httpx

GITHUB_API_BASE = "https://api.github.com"


class GithubSyncError(Exception):
    """Raised when the GitHub API is unreachable or returns an unexpected
    response. GitHub's REST API is stable/official, so unlike LeetCode this
    is not expected to fire often — but we still don't want it to surface
    as a raw, unhandled exception at the API layer.
    """


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def fetch_repos(client: httpx.AsyncClient, username: str, token: str) -> list[dict]:
    """List all public (and, if token has scope, private) repos for the user."""
    repos: list[dict] = []
    page = 1
    while True:
        resp = await client.get(
            f"{GITHUB_API_BASE}/user/repos",
            headers=_auth_headers(token),
            params={"per_page": 100, "page": page, "affiliation": "owner"},
        )
        if resp.status_code != 200:
            raise GithubSyncError(f"GET /user/repos failed: {resp.status_code} {resp.text}")
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


async def fetch_languages(client: httpx.AsyncClient, owner: str, repo: str, token: str) -> dict:
    """Byte-count per language for a single repo, e.g. {"Python": 40213, "HTML": 1523}."""
    resp = await client.get(
        f"{GITHUB_API_BASE}/repos/{owner}/{repo}/languages",
        headers=_auth_headers(token),
    )
    if resp.status_code != 200:
        # Non-fatal: a repo with no code (empty repo) can 404/409 here.
        return {}
    return resp.json()


async def fetch_commit_count_last_30d(
    client: httpx.AsyncClient, owner: str, repo: str, username: str, token: str
) -> int:
    """Count commits authored by `username` in the last 30 days.
    Capped at 500 commits (5 pages) to avoid pathological pagination
    on very active repos — plenty for a confidence/activity signal.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    count = 0
    page = 1
    while page <= 5:
        resp = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits",
            headers=_auth_headers(token),
            params={"since": since, "author": username, "per_page": 100, "page": page},
        )
        if resp.status_code == 409:
            # Empty repository — no commits at all.
            return 0
        if resp.status_code != 200:
            raise GithubSyncError(
                f"GET /repos/{owner}/{repo}/commits failed: {resp.status_code} {resp.text}"
            )
        batch = resp.json()
        if not batch:
            break
        count += len(batch)
        if len(batch) < 100:
            break
        page += 1
    return count