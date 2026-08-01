# backend/app/services/projects/overview.py
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.projects.scoring import compute_rating, compute_status, compute_tier, derive_engineering_tags
from app.services.projects.repo_linking import build_repo_lookup
from app.services.projects.claim_audit import audit_project_claims
from app.services.projects.linking import normalize_name  # <-- NEW IMPORT

from app.models.facts import GithubSnapshot, Project
from app.models.github_analysis import GithubProjectAnalysis
from app.models.structure import Capability, ProjectCapability, ProjectSkill, Skill
from app.schemas.projects import ProjectCard, ProjectsOverviewResponse, ProjectsStats

ABANDONMENT_STALE_DAYS = 60
ABANDONMENT_QUALITY_FLOOR = 45


def _fallback_tagline(name: str, description: str | None) -> str:
    if description:
        first_sentence = description.strip().split(".")[0].strip()
        if first_sentence:
            return first_sentence if len(first_sentence) <= 80 else first_sentence[:77].rstrip() + "..."
    return name


def _compute_abandonment_status(matched_analysis) -> str | None:
    if matched_analysis is None or matched_analysis.is_active:
        return None
    stale = (matched_analysis.last_activity_days or 0) > ABANDONMENT_STALE_DAYS
    if not stale:
        return None
    return "resume_it" if matched_analysis.quality_score >= ABANDONMENT_QUALITY_FLOOR else "retire_it"


async def build_projects_overview(db: AsyncSession, user_id) -> ProjectsOverviewResponse:
    projects_result = await db.execute(
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
    )
    all_projects = list(projects_result.scalars().all())

    # --- FIX: dedupe by normalized project name, same pattern already
    # used by profile.py's get_profile_data() and
    # career_planner/context_builder.py's _get_projects(). Without this,
    # every resume re-upload creates a brand-new Project row for the same
    # conceptual project (ingestion.py never checks for an existing one —
    # that's correct for an append-only facts table), and this page was
    # rendering every single one of them as a separate card. Since the
    # query above orders by created_at desc, keeping the FIRST occurrence
    # of each normalized name keeps the most recently uploaded version.
    seen_names: set[str] = set()
    projects: list[Project] = []
    for p in all_projects:
        norm = normalize_name(p.name)
        if norm not in seen_names:
            seen_names.add(norm)
            projects.append(p)

    if not projects:
        return ProjectsOverviewResponse(stats=ProjectsStats(), projects=[])

    project_ids = [p.id for p in projects]

    skill_rows = await db.execute(
        select(ProjectSkill.project_id, Skill.name, Skill.canonical_name)
        .join(Skill, ProjectSkill.skill_id == Skill.id)
        .where(ProjectSkill.project_id.in_(project_ids))
    )
    skills_by_project: dict = {}
    all_skill_canonicals: set[str] = set()
    for project_id, name, canonical in skill_rows.all():
        skills_by_project.setdefault(project_id, []).append({"name": name, "canonical": canonical})
        all_skill_canonicals.add(canonical)

    capability_rows = await db.execute(
        select(ProjectCapability.project_id, Capability.name)
        .join(Capability, ProjectCapability.capability_id == Capability.id)
        .where(ProjectCapability.project_id.in_(project_ids))
    )
    capabilities_by_project: dict = {}
    all_capability_names: set[str] = set()
    for project_id, name in capability_rows.all():
        capabilities_by_project.setdefault(project_id, []).append(name)
        all_capability_names.add(name)

    analysis_rows = await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)
    )
    analysis_by_repo_name = {a.repo_name: a for a in analysis_rows.scalars().all()}

    repo_lookup = build_repo_lookup(analysis_by_repo_name, projects)

    connected_repos_result = await db.execute(
        select(func.count(func.distinct(GithubSnapshot.repo_name))).where(GithubSnapshot.user_id == user_id)
    )
    connected_repositories = connected_repos_result.scalar_one() or 0

    cards: list[ProjectCard] = []
    claim_risk_count = 0
    for p in projects:
        project_skills = skills_by_project.get(p.id, [])
        project_capabilities = capabilities_by_project.get(p.id, [])
        matched_repo_name = repo_lookup.get(p.id)
        matched_analysis = analysis_by_repo_name.get(matched_repo_name) if matched_repo_name else None

        rating = compute_rating(
            description_length=len(p.description or ""),
            skill_count=len(project_skills),
            capability_count=len(project_capabilities),
            github_quality_score=matched_analysis.quality_score if matched_analysis else None,
            github_activity_score=matched_analysis.activity_score if matched_analysis else None,
        )
        status = compute_status(matched_analysis.is_active if matched_analysis else None)
        has_repo = matched_analysis is not None or bool(p.repo_url)

        engineering_tags = derive_engineering_tags(
            p.stack or [s["name"] for s in project_skills],
            extra_capabilities=list(project_capabilities) + (matched_analysis.capabilities if matched_analysis else []),
        )
        tier = compute_tier(rating, has_repo=has_repo, github_tier=matched_analysis.tier if matched_analysis else None)

        claim_risk = None
        if matched_analysis is not None:
            audit = audit_project_claims(
                project_name=p.name,
                project_stack=p.stack or [],
                project_description=p.description,
                repo_technologies=matched_analysis.technologies or [],
                repo_capabilities=matched_analysis.capabilities or [],
                architecture_assessment=matched_analysis.architecture_assessment,
                has_tests=matched_analysis.has_tests,
                has_ci=matched_analysis.has_ci,
                quality_score=matched_analysis.quality_score,
                activity_score=matched_analysis.activity_score,
            )
            if audit["unsupported_claims"]:
                claim_risk = "high" if len(audit["unsupported_claims"]) > 1 else "medium"
                claim_risk_count += 1
            elif audit["undersold_work"]:
                claim_risk = "undersold"

        abandonment_status = _compute_abandonment_status(matched_analysis)

        cards.append(
            ProjectCard(
                id=str(p.id),
                name=p.name,
                tagline=p.tagline or _fallback_tagline(p.name, p.description),
                description=p.description,
                stack=(p.stack or [s["name"] for s in project_skills])[:6],
                capabilities=list(project_capabilities),
                engineering_tags=engineering_tags,
                tier=tier,
                is_featured=False,
                status=status,
                rating=rating,
                updated_at=p.updated_at or p.created_at,
                repo_url=p.repo_url,
                has_repo=has_repo,
                matched_repo_name=matched_repo_name,
                claim_risk=claim_risk,
                abandonment_status=abandonment_status,
                collaboration_mode=matched_analysis.collaboration_mode if matched_analysis else None,
                commit_hygiene_score=matched_analysis.commit_hygiene_score if matched_analysis else None,
            )
        )

    featured_count = min(4, len(cards))
    # Explicit tiebreaker: rating first, then most-recently-updated. Previously
    # this relied on Python's stable sort silently preserving the created_at-desc
    # order the initial query happened to return cards in — correct in practice,
    # but not something a reader could tell without checking sort stability.
    ranked = sorted(cards, key=lambda c: (c.rating, c.updated_at), reverse=True)
    featured_ids = {c.id for c in ranked[:featured_count] if c.rating >= 3.0}
    for c in cards:
        c.is_featured = c.id in featured_ids

    cards.sort(key=lambda c: c.updated_at, reverse=True)

    resume_backed = sum(1 for p in projects if p.resume_id is not None)
    github_backed = sum(1 for c in cards if c.has_repo)
    flagship_count = sum(1 for c in cards if c.tier == "Flagship Project")

    stats = ProjectsStats(
        total=len(cards),
        flagship=flagship_count,
        technologies=len(all_skill_canonicals),
        resume_coverage_pct=round((resume_backed / len(cards)) * 100) if cards else 0.0,
        github_coverage_pct=round((github_backed / len(cards)) * 100) if cards else 0.0,
        capabilities=len(all_capability_names),
        connected_repositories=connected_repositories,
        claim_risk_count=claim_risk_count,
    )

    return ProjectsOverviewResponse(stats=stats, projects=cards)