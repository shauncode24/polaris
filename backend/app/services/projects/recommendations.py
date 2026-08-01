"""Deterministic recommendation engine — reworked to (a) use
GithubProjectAnalysis's VERIFIED has_tests/has_ci/has_readme instead of
re-deriving a weaker signal from the resume-parsed stack array, and
(b) rank suggestions by a REAL score-point impact, mirroring
github_insights.py's build_ranked_recommendations, applied to the
Projects module instead of being GitHub-only.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_analysis import GithubProjectAnalysis
from app.schemas.projects import RecommendationItem
from app.services.projects.overview import build_projects_overview

RAG_CAPABILITY_HINTS = {"rag", "vector search", "ai integration"}

# Impact constants mirror the EXACT point values awarded by score_repository()
# in github_scoring.py — keep in sync with github_insights._IMPACT_* constants:
#   documentation: has_readme -> +10 pts  (score_repository: documentation += 10.0)
#   engineering:   has_tests  -> +12 pts  (score_repository: engineering += 12.0)
#   engineering:   has_ci     -> +8 pts   (score_repository: engineering += 8.0)
IMPACT_MISSING_README = 10
IMPACT_MISSING_TESTS = 12
IMPACT_MISSING_CI = 8
IMPACT_CLAIM_RISK = 10
IMPACT_STALE_HIGH_QUALITY = 6
IMPACT_CONNECT_REPO = 6
IMPACT_RAG_BENCHMARK = 4
IMPACT_FALLBACK = 2


def _has_capability(project, keywords: set[str]) -> bool:
    lowered = {c.lower() for c in project.capabilities}
    return any(any(k in c for k in keywords) for c in lowered)


async def build_project_recommendations(db: AsyncSession, user_id, overview=None) -> list[RecommendationItem]:
    overview = overview or await build_projects_overview(db, user_id)

    analysis_result = await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)
    )
    analysis_by_repo_name = {a.repo_name: a for a in analysis_result.scalars().all()}

    candidates: list[dict] = []

    for project in overview.projects:
        matched = analysis_by_repo_name.get(project.matched_repo_name) if project.matched_repo_name else None

        if matched is not None:
            # Verified signal — never re-derive this from the resume
            # stack array, which is exactly what the old implementation did.
            if not matched.has_tests:
                candidates.append({"text": f"Add automated tests to {project.name}", "impact": IMPACT_MISSING_TESTS})
            if not matched.has_ci:
                candidates.append({"text": f"Add CI to {project.name}", "impact": IMPACT_MISSING_CI})
            if not matched.has_readme:
                candidates.append({"text": f"Write a clearer README for {project.name}", "impact": IMPACT_MISSING_README})
        else:
            # No verified repo match — fall back to the resume-parsed
            # stack, a much weaker signal but still better than nothing.
            stack_lower = {s.lower() for s in project.stack}
            if "testing" not in stack_lower and not _has_capability(project, {"testing"}):
                candidates.append({
                    "text": f"Add a test suite to {project.name}",
                    "impact": IMPACT_MISSING_TESTS // 2,
                })

        if not project.description or len(project.description) < 60:
            candidates.append({"text": f"Publish {project.name} with a clear README", "impact": IMPACT_MISSING_README})

        stack_lower = {s.lower() for s in project.stack}
        if _has_capability(project, RAG_CAPABILITY_HINTS) or "rag" in stack_lower:
            candidates.append({"text": f"Benchmark the {project.name} retrieval path", "impact": IMPACT_RAG_BENCHMARK})

        if not project.has_repo:
            candidates.append({"text": f"Connect {project.name} to a GitHub repository", "impact": IMPACT_CONNECT_REPO})

        if project.claim_risk in ("high", "medium"):
            candidates.append({
                "text": f"Reconcile your resume claims for {project.name} with what the repo actually shows",
                "impact": IMPACT_CLAIM_RISK,
            })

        if project.abandonment_status == "resume_it":
            candidates.append({
                "text": f"Resume work on {project.name} — it's high-quality but stale",
                "impact": IMPACT_STALE_HIGH_QUALITY,
            })

    if not candidates:
        candidates.append({"text": "Add architecture diagrams to your strongest project", "impact": IMPACT_FALLBACK})

    candidates.sort(key=lambda c: c["impact"], reverse=True)
    return [RecommendationItem(text=c["text"], impact=c["impact"]) for c in candidates[:4]]