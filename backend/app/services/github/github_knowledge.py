from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import ProfileSnapshot

MAX_REPOS_IN_KNOWLEDGE = 15


async def _get_latest_github_snapshot(db: AsyncSession, user_id) -> ProfileSnapshot | None:
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note == "github sync")
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def build_github_knowledge_object(db: AsyncSession, user_id) -> dict | None:
    """Condenses the deterministic GitHub analysis (github_analyzer.py's
    per-repo output, stored in GithubProjectAnalysis, plus the latest
    sync's aggregate summary/insights from github_insights.py) into a
    compact, career-focused object for the LLM. This is the ONLY thing
    the portfolio-review LLM call ever sees — never the raw GitHub API
    payload — which keeps the call cheap, keeps outputs stable, and
    means the model can only reason over evidence code has already
    verified, never over raw file trees or manifests.
    """
    snapshot = await _get_latest_github_snapshot(db, user_id)
    if snapshot is None or not isinstance(snapshot.skills_json, dict):
        return None

    payload = snapshot.skills_json
    summary = payload.get("summary", {})
    insights = payload.get("insights", {})
    repositories = payload.get("repositories", [])

    analysis_result = await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)
    )
    analysis_by_repo = {a.repo_name: a for a in analysis_result.scalars().all()}

    # Rank by the same quality+activity signal github_analyzer.py already
    # uses for flagship tiering, so the model sees the strongest evidence
    # first instead of working through every synced repo.
    def _rank_key(repo: dict) -> float:
        a = analysis_by_repo.get(repo["name"])
        if a is None:
            return repo.get("project_score", {}).get("overall", 0)
        return a.quality_score * 0.6 + a.activity_score * 0.4

    ranked = sorted(repositories, key=_rank_key, reverse=True)[:MAX_REPOS_IN_KNOWLEDGE]

    repo_summaries = []
    for repo in ranked:
        a = analysis_by_repo.get(repo["name"])
        repo_summaries.append({
            "name": repo["name"],
            "description": repo.get("description"),
            "languages": repo.get("languages", []),
            "technologies": a.technologies if a else [],
            "capabilities": a.capabilities if a else [],
            "category": a.category if a else None,
            "tier": repo.get("tier"),
            "quality_score": a.quality_score if a else None,
            "activity_score": a.activity_score if a else None,
            "has_readme": repo.get("has_readme"),
            "has_tests": repo.get("has_tests"),
            "has_ci": repo.get("has_ci"),
            "commits_last_30_days": repo.get("commits_last_30_days"),
            "is_active": a.is_active if a else None,
            "archived": repo.get("archived"),
        })

    all_technologies = sorted({t for a in analysis_by_repo.values() for t in (a.technologies or [])})
    all_capabilities = sorted({c for a in analysis_by_repo.values() for c in (a.capabilities or [])})

    return {
        "summary": {
            "repos_synced": summary.get("repos_synced"),
            "total_commits_last_30_days": summary.get("total_commits_last_30_days"),
            "languages_detected": [l["language"] for l in summary.get("languages_detected", [])[:8]],
        },
        "engineering_practices": insights.get("engineering_practices", {}),
        "portfolio_profile": insights.get("portfolio_profile", {}),
        "all_technologies": all_technologies,
        "all_capabilities": all_capabilities,
        "repositories": repo_summaries,
    }