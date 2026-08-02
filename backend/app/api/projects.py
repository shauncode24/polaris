from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import GithubSnapshot, Project, User
from app.models.structure import ProjectCapability
from app.models.github_analysis import GithubProjectAnalysis
from app.schemas.projects import ProjectsInsightsResponse, ProjectsOverviewResponse, LinkProjectRequest
from app.schemas.project_intelligence import (
    ClaimAuditReport,
    InterviewQuestionsReport,
    PortfolioComparisonResponse,
    PortfolioNarrativeReport,
    ProjectIntelligenceReport,
)
from app.services.projects.claim_audit import audit_project_claims
from app.services.projects.claim_audit_llm import generate_claim_audit_narrative, get_cached_claim_audit_report
from app.services.projects.comparison import build_goal_aware_ranking, build_projects_comparison
from app.services.projects.intelligence import build_project_context, generate_project_intelligence
from app.services.projects.interview_questions import (
    generate_and_cache_interview_questions,
    get_cached_interview_questions,
)
from app.services.projects.milestones import build_recent_milestones
from app.services.projects.overview import build_projects_overview
from app.services.projects.portfolio_narrative import generate_portfolio_narrative, get_latest_portfolio_narrative
from app.services.projects.recommendations import build_project_recommendations
from app.services.projects.linking import suggest_repo_links, link_project, unlink_project

from app.services.identity.identity_refresh import trigger_identity_refresh

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
    comparison = await build_projects_comparison(db, current_user.id, overview=overview)
    recommendations = await build_project_recommendations(db, current_user.id, overview=overview)
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
    job_description_id: UUID | None = None,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Full goal/JD-aware ranking across the entire portfolio — not just
    a pairwise top-2 comparison. Scores against a specific target job when
    job_description_id is given, otherwise the user's most recently
    analyzed job.
    """
    return await build_goal_aware_ranking(db, current_user.id, job_description_id)


@router.get("/portfolio-narrative", response_model=PortfolioNarrativeReport)
async def get_portfolio_narrative(
    regenerate: bool = False,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Portfolio-wide engineering-maturity narrative, gated behind a
    minimum verified-project count so the LLM is never spent narrating
    a portfolio with too little real signal to say anything specific.
    """
    if not regenerate:
        cached = await get_latest_portfolio_narrative(db, current_user.id)
        if cached is not None:
            return cached
    return await generate_portfolio_narrative(db, current_user.id)


@router.get("/{project_id}/claim-audit", response_model=ClaimAuditReport)
async def get_project_claim_audit(
    project_id: UUID,
    regenerate: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Diffs this project's resume claims (stack/description) against
    its real, GitHub-verified technologies/capabilities/architecture —
    the single highest-value missing feature flagged in the Projects
    module review.
    """
    if not regenerate:
        cached = await get_cached_claim_audit_report(db, project_id)
        if cached is not None:
            return cached

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
    report = await generate_claim_audit_narrative(db, current_user.id, project_id, facts)

    # Freshness fix (Important, Engineering Identity audit): a Claim
    # Audit run can change claim_risk_details, which top_skills'
    # confidence is now reconciled against — this was previously the
    # one signal in IdentityFacts most related to the confidence/
    # contradiction problem that never triggered a refresh at all.
    await trigger_identity_refresh(db, current_user.id, "claim audit")

    return report

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
    regenerate: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not regenerate:
        cached = await get_cached_interview_questions(db, project_id)
        if cached is not None:
            return cached

    context = await build_project_context(db, current_user.id, project_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return await generate_and_cache_interview_questions(db, current_user.id, project_id, context)


@router.get("/link-suggestions")
async def get_link_suggestions_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await suggest_repo_links(db, current_user.id)


@router.get("/link-options")
async def get_link_options(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GithubProjectAnalysis.repo_name)
        .where(GithubProjectAnalysis.user_id == current_user.id)
        .order_by(GithubProjectAnalysis.repo_name.asc())
    )
    repos = [r[0] for r in result.all()]
    return {"repositories": repos}


@router.post("/{project_id}/link")
async def confirm_project_link(
    project_id: UUID,
    payload: LinkProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await link_project(db, current_user.id, project_id, payload.repo_name)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Freshness fix — confirming a repo link can newly enable (or change
    # the target of) a Claim Audit finding for this project, which
    # claim_risk_details/top_skills reconciliation depends on.
    await trigger_identity_refresh(db, current_user.id, "project link confirmed")

    return {"status": "success", "github_repo_name": project.github_repo_name}

@router.post("/{project_id}/unlink")
async def remove_project_link(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await unlink_project(db, current_user.id, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Freshness fix — removing a repo link can retire a previously-real
    # claim-risk finding for this project.
    await trigger_identity_refresh(db, current_user.id, "project link removed")

    return {"status": "success"}