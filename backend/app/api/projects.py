from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import GithubSnapshot, Project, User
from app.models.structure import ProjectCapability
from app.schemas.projects import ProjectsInsightsResponse, ProjectsOverviewResponse
from app.schemas.project_intelligence import (
    ClaimAuditReport,
    InterviewQuestionsReport,
    PortfolioComparisonResponse,
    PortfolioNarrativeReport,
    ProjectIntelligenceReport,
)
from app.services.projects.claim_audit import audit_project_claims
from app.services.projects.claim_audit_llm import generate_claim_audit_narrative
from app.services.projects.comparison import build_goal_aware_ranking, build_projects_comparison
from app.services.projects.intelligence import build_project_context, generate_project_intelligence
from app.services.projects.interview_questions import generate_interview_questions
from app.services.projects.milestones import build_recent_milestones
from app.services.projects.overview import build_projects_overview
from app.services.projects.portfolio_narrative import generate_portfolio_narrative
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


@router.get("/ranking", response_model=PortfolioComparisonResponse)
async def get_goal_aware_ranking(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Full goal/JD-aware ranking across the entire portfolio — not just
    a pairwise top-2 comparison. Scores every project against the user's
    most recent target job's requirements when one exists.
    """
    return await build_goal_aware_ranking(db, current_user.id)


@router.get("/portfolio-narrative", response_model=PortfolioNarrativeReport)
async def get_portfolio_narrative(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Portfolio-wide engineering-maturity narrative, gated behind a
    minimum verified-project count so the LLM is never spent narrating
    a portfolio with too little real signal to say anything specific.
    """
    return await generate_portfolio_narrative(db, current_user.id)


@router.get("/{project_id}/claim-audit", response_model=ClaimAuditReport)
async def get_project_claim_audit(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Diffs this project's resume claims (stack/description) against
    its real, GitHub-verified technologies/capabilities/architecture —
    the single highest-value missing feature flagged in the Projects
    module review.
    """
    context = await build_project_context(db, current_user.id, project_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not context["has_repo_match"]:
        raise HTTPException(
            status_code=400,
            detail="This project has no matched GitHub repository yet — sync GitHub and/or set a repo_url first.",
        )

    verified = context["verified"]
    facts = audit_project_claims(
        project_name=context["name"],
        project_stack=context["stack"],
        project_description=context["description"],
        repo_technologies=verified.get("technologies", []),
        repo_capabilities=verified.get("capabilities", []),
        architecture_assessment=verified.get("architecture_assessment"),
        has_tests=verified.get("has_tests"),
        has_ci=verified.get("has_ci"),
        quality_score=verified.get("quality_score"),
        activity_score=verified.get("activity_score"),
    )
    return await generate_claim_audit_narrative(facts)


@router.get("/{project_id}/intelligence", response_model=ProjectIntelligenceReport)
async def get_project_intelligence(
    project_id: UUID,
    framing: str = Query(
        "Explain this project in technical depth, as if I'm interviewing at a top-tier tech company."
    ),
    comparison_target: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The Project Intelligence agent promised in the design doc's §6.1
    but never built — a framing-specific, deeply grounded explanation
    or comparison of one real project.
    """
    try:
        return await generate_project_intelligence(db, current_user.id, project_id, framing, comparison_target)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{project_id}/interview-questions", response_model=InterviewQuestionsReport)
async def get_project_interview_questions(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    context = await build_project_context(db, current_user.id, project_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return await generate_interview_questions(context)