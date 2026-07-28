from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.projects import RecommendationItem
from app.services.projects.overview import build_projects_overview

RAG_CAPABILITY_HINTS = {"rag", "vector search", "ai integration"}


def _has_capability(project, keywords: set[str]) -> bool:
    lowered = {c.lower() for c in project.capabilities}
    return any(any(k in c for k in keywords) for c in lowered)


async def build_project_recommendations(db: AsyncSession, user_id) -> list[RecommendationItem]:
    overview = await build_projects_overview(db, user_id)
    suggestions: list[RecommendationItem] = []

    for project in overview.projects:
        stack_lower = {s.lower() for s in project.stack}

        if "testing" not in stack_lower and not _has_capability(project, {"testing"}):
            suggestions.append(RecommendationItem(text=f"Add a test suite to {project.name}"))

        if not project.description or len(project.description) < 60:
            suggestions.append(RecommendationItem(text=f"Publish {project.name} with a clear README"))

        if _has_capability(project, RAG_CAPABILITY_HINTS) or "rag" in stack_lower:
            suggestions.append(RecommendationItem(text=f"Benchmark the {project.name} retrieval path"))

        if not project.has_repo:
            suggestions.append(RecommendationItem(text=f"Connect {project.name} to a GitHub repository"))

    if not suggestions:
        suggestions.append(RecommendationItem(text="Add architecture diagrams to your strongest project"))

    # Cap so the panel stays a short, scannable list rather than one per project.
    return suggestions[:4]