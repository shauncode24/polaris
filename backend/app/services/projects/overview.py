from app.api import projects
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.projects.scoring import compute_rating, compute_status, compute_tier, derive_engineering_tags
from app.services.projects.linking import normalize_name

from app.models.facts import GithubSnapshot, Project
from app.models.github_analysis import GithubProjectAnalysis
from app.models.structure import Capability, ProjectCapability, ProjectSkill, Skill
from app.schemas.projects import ProjectCard, ProjectsOverviewResponse, ProjectsStats


def _fallback_tagline(name: str, description: str | None) -> str:
    if description:
        first_sentence = description.strip().split(".")[0].strip()
        if first_sentence:
            return first_sentence if len(first_sentence) <= 80 else first_sentence[:77].rstrip() + "..."
    return name


async def build_projects_overview(db: AsyncSession, user_id) -> ProjectsOverviewResponse:
    projects_result = await db.execute(
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
    )
    all_projects = list(projects_result.scalars().all())

    # De-duplicate by normalized project name, keeping the most recent one
    seen_names = set()
    projects = []
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
    # Only used to flag an UNCONFIRMED possible match for the UI — never
    # to enrich rating/tier/tags. See services/projects/linking.py.
    normalized_repo_lookup = {normalize_name(name): name for name in analysis_by_repo_name}

    connected_repos_result = await db.execute(
        select(func.count(func.distinct(GithubSnapshot.repo_name))).where(GithubSnapshot.user_id == user_id)
    )
    connected_repositories = connected_repos_result.scalar_one() or 0

    cards: list[ProjectCard] = []
    for p in projects:
        project_skills = skills_by_project.get(p.id, [])
        project_capabilities = capabilities_by_project.get(p.id, [])

        # Explicit link only — this is the fix for the silent
        # `.lower()` name-match failure mode described in linking.py.
        matched_analysis = None
        if p.github_repo_name:
            matched_analysis = analysis_by_repo_name.get(p.github_repo_name)
            link_status = "confirmed" if matched_analysis else "broken_link"
        else:
            guessed_repo = normalized_repo_lookup.get(normalize_name(p.name))
            link_status = "suggested_match" if guessed_repo else "unmatched"

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
                link_status=link_status,
                github_repo_name=p.github_repo_name,
            )
        )

    featured_count = min(4, len(cards))
    ranked = sorted(cards, key=lambda c: c.rating, reverse=True)
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
    )

    return ProjectsOverviewResponse(stats=stats, projects=cards)