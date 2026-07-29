from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import GithubSnapshot, Project, User, Resume
from app.models.structure import ProjectCapability
from app.schemas.projects import (
    LinkProjectRequest,
    LinkSuggestion,
    ProjectsInsightsResponse,
    ProjectsOverviewResponse,
)
from app.schemas.project_intelligence import ProjectComparisonReport, ProjectIntelligenceReport
from app.services.projects.comparison import build_projects_comparison
from app.services.projects.curation import compute_curation
from app.services.projects.linking import link_project, suggest_repo_links, unlink_project, normalize_name
from app.services.projects.milestones import build_recent_milestones
from app.services.projects.overview import build_projects_overview
from app.services.projects.project_intelligence import (
    ProjectIntelligenceError,
    generate_project_comparison,
    generate_project_explanation,
    get_project_intelligence_history,
)
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
    overview = await build_projects_overview(db, current_user.id)
    comparison = await build_projects_comparison(db, current_user.id)
    recommendations = await build_project_recommendations(db, current_user.id)
    milestones = await build_recent_milestones(db, current_user.id)
    curation = compute_curation(overview.projects)

    project_rows_result = await db.execute(
        select(Project.id, Project.name, Project.resume_id)
        .where(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    all_rows = project_rows_result.all()

    seen_names = set()
    project_rows = []
    for row in all_rows:
        norm = normalize_name(row[1])
        if norm not in seen_names:
            seen_names.add(norm)
            project_rows.append(row)

    project_ids = [row[0] for row in project_rows]
    resume_backed_projects = sum(1 for row in project_rows if row[2] is not None)

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
        curation=curation,
    )


# ── Explicit linking ──────────────────────────────────────────────────

@router.get("/link-suggestions", response_model=list[LinkSuggestion])
async def get_link_suggestions(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await suggest_repo_links(db, current_user.id)


@router.post("/{project_id}/link")
async def confirm_project_link(
    project_id: str,
    payload: LinkProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await link_project(db, current_user.id, project_id, payload.repo_name)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"status": "linked", "project_id": str(project.id), "github_repo_name": project.github_repo_name}


@router.delete("/{project_id}/link")
async def remove_project_link(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await unlink_project(db, current_user.id, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"status": "unlinked", "project_id": str(project.id)}


# ── Project Intelligence ──────────────────────────────────────────────

@router.post("/{project_id}/intelligence/explain", response_model=ProjectIntelligenceReport)
async def explain_project(
    project_id: str,
    framing: str = "general",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await generate_project_explanation(db, current_user.id, project_id, framing)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ProjectIntelligenceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/{project_id}/intelligence/compare", response_model=ProjectComparisonReport)
async def compare_project(
    project_id: str,
    comparison_target: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await generate_project_comparison(db, current_user.id, project_id, comparison_target)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ProjectIntelligenceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{project_id}/intelligence")
async def get_project_intelligence(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_project_intelligence_history(db, current_user.id, project_id)