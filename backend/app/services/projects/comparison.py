from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.projects import ComparisonMetric, ProjectComparison
from app.services.projects.overview import build_projects_overview
from app.services.projects.scoring import AI_SKILLS, BACKEND_SKILLS


def _winner(a_name: str, b_name: str, a_value: float, b_value: float) -> str:
    if a_value == b_value:
        return "Tie"
    return a_name if a_value > b_value else b_name


async def build_projects_comparison(db: AsyncSession, user_id) -> ProjectComparison | None:
    overview = await build_projects_overview(db, user_id)
    candidates = sorted(overview.projects, key=lambda c: c.rating, reverse=True)[:2]
    if len(candidates) < 2:
        return None

    a, b = candidates[0], candidates[1]
    a_stack = {s.lower() for s in a.stack}
    b_stack = {s.lower() for s in b.stack}

    complexity_winner = _winner(
        a.name, b.name, len(a.stack) + len(a.capabilities), len(b.stack) + len(b.capabilities)
    )
    ai_winner = _winner(a.name, b.name, len(a_stack & AI_SKILLS), len(b_stack & AI_SKILLS))
    backend_winner = _winner(a.name, b.name, len(a_stack & BACKEND_SKILLS), len(b_stack & BACKEND_SKILLS))
    interview_winner = _winner(a.name, b.name, a.rating, b.rating)

    metrics = [
        ComparisonMetric(label="More complex", winner=complexity_winner),
        ComparisonMetric(label="Deeper AI", winner=ai_winner),
        ComparisonMetric(label="Stronger backend", winner=backend_winner),
        ComparisonMetric(label="Better interview value", winner=interview_winner),
    ]

    lead_project = complexity_winner if complexity_winner != "Tie" else a.name
    support_project = b.name if lead_project == a.name else a.name
    recommendation = (
        f"Lead with {lead_project} for backend and AI interviews; use {support_project} "
        f"to show breadth and product delivery."
    )

    return ProjectComparison(
        project_a=a.name, project_b=b.name, metrics=metrics, recommendation=recommendation
    )