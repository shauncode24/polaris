from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import GithubSnapshot, Project, User
from app.models.structure import ProjectCapability
from app.schemas.projects import ProjectsInsightsResponse, ProjectsOverviewResponse
from app.services.projects.comparison import build_projects_comparison
from app.services.projects.milestones import build_recent_milestones
from app.services.projects.overview import build_projects_overview
from app.services.projects.recommendations import build_project_recommendations

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectsOverviewResponse)
async def list_projects(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await build_projects_overview(db, current_user.id)


@router.get("/insights", response_model=ProjectsInsightsResponse)
async def get_projects_insights(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    comparison = await build_projects_comparison(db, current_user.id)
    recommendations = await build_project_recommendations(db, current_user.id)
    milestones = await build_recent_milestones(db, current_user.id)

    project_rows_result = await db.execute(
        select(Project.id, Project.resume_id).where(Project.user_id == current_user.id)
    )
    project_rows = project_rows_result.all()
    project_ids = [row[0] for row in project_rows]
    resume_backed_projects = sum(1 for row in project_rows if row[1] is not None)

    capability_count = 0
    if project_ids:
        cap_result = await db.execute(
            select(func.count(func.distinct(ProjectCapability.capability_id)))
            .where(ProjectCapability.project_id.in_(project_ids))
        )
        capability_count = cap_result.scalar_one() or 0

    connected_repos_result = await db.execute(
        select(func.count(func.distinct(GithubSnapshot.repo_name)))
        .where(GithubSnapshot.user_id == current_user.id)
    )
    connected_repositories = connected_repos_result.scalar_one() or 0

    source_coverage = {
        "resume_uploads": resume_backed_projects,
        "connected_repositories": connected_repositories,
        "capabilities_evidenced": capability_count,
    }

    return ProjectsInsightsResponse(
        comparison=comparison,
        recommendations=recommendations,
        milestones=milestones,
        source_coverage=source_coverage,
    )