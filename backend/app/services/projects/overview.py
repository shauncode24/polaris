import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.projects.scoring import compute_rating, compute_status, compute_tier, derive_engineering_tags

from app.models.facts import GithubSnapshot, Project, Resume, User
from app.models.github_analysis import GithubProjectAnalysis
from app.models.structure import Capability, ProjectCapability, ProjectSkill, Skill
from app.schemas.projects import ProjectCard, ProjectsOverviewResponse, ProjectsStats


def _fallback_tagline(name: str, description: str | None) -> str:
    if description:
        first_sentence = description.strip().split(".")[0].strip()
        if first_sentence:
            return first_sentence if len(first_sentence) <= 80 else first_sentence[:77].rstrip() + "..."
    return name


def _normalize_name(name: str) -> str:
    """Strips everything but letters/digits and lowercases, so 'Campus Intel',
    'campus-intelligence', and 'Project 1: Campus Intel' all reduce to a
    comparable token instead of requiring an exact match.
    """
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _names_match(resume_name: str, repo_name: str, repo_url: str | None) -> bool:
    """Fuzzy match: a resume project counts as 'the same thing' as a synced
    repo if their normalized names overlap in either direction, or if the
    repo name literally appears in the project's stored repo_url. This is
    deliberately generous — a false negative here just means the repo shows
    up as its own (harmless, extra) card; a false positive would wrongly
    hide a real repo, which is the worse failure mode.
    """
    normalized_resume = _normalize_name(resume_name)
    normalized_repo = _normalize_name(repo_name)
    if normalized_resume and normalized_repo:
        if normalized_resume == normalized_repo:
            return True
        if normalized_repo in normalized_resume or normalized_resume in normalized_repo:
            return True
    if repo_url and repo_name.lower() in repo_url.lower():
        return True
    return False


def _card_from_resume_project(p: Project, project_skills: list[dict], project_capabilities: list[str], matched_analysis) -> ProjectCard:
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

    return ProjectCard(
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
        repo_url=p.repo_url or (f"https://github.com/{matched_analysis.repo_name}" if False else p.repo_url),
        has_repo=has_repo,
    )


def _card_from_github_only(a: GithubProjectAnalysis, github_username: str | None) -> ProjectCard:
    """A synced GitHub repo that doesn't correspond to any resume-listed
    project. Built purely from GithubProjectAnalysis — no Project row
    backs this card, so `id` is prefixed to stay distinguishable and
    `repo_url` is reconstructed from the known username since
    GithubProjectAnalysis itself doesn't store one.
    """
    rating = compute_rating(
        description_length=0,
        skill_count=len(a.technologies or []),
        capability_count=len(a.capabilities or []),
        github_quality_score=a.quality_score,
        github_activity_score=a.activity_score,
    )
    status = compute_status(a.is_active)
    engineering_tags = derive_engineering_tags(a.technologies or [], extra_capabilities=a.capabilities or [])
    tier = compute_tier(rating, has_repo=True, github_tier=a.tier)
    repo_url = f"https://github.com/{github_username}/{a.repo_name}" if github_username else None

    return ProjectCard(
        id=f"gh-{a.id}",
        name=a.repo_name,
        tagline=f"{a.category} project on GitHub" if a.category else a.repo_name,
        description=None,
        stack=(a.technologies or [])[:6],
        capabilities=list(a.capabilities or []),
        engineering_tags=engineering_tags,
        tier=tier,
        is_featured=False,
        status=status,
        rating=rating,
        updated_at=a.computed_at,
        repo_url=repo_url,
        has_repo=True,
    )


async def build_projects_overview(db: AsyncSession, user_id) -> ProjectsOverviewResponse:
    # Only pull resume-sourced projects from the MOST RECENT resume (plus
    # any manually-added project with no resume_id at all). Every past
    # resume upload permanently leaves its Project rows behind, and the
    # old query pulled every resume's projects at once — that's what was
    # producing the repeated/near-duplicate cards ("Flood Alert" and
    # "Project 2: Flood Alert" both existing simultaneously).
    latest_resume_result = await db.execute(
        select(Resume.id).where(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(1)
    )
    latest_resume_id = latest_resume_result.scalar_one_or_none()

    projects_query = select(Project).where(Project.user_id == user_id)
    if latest_resume_id is not None:
        projects_query = projects_query.where(
            (Project.resume_id == latest_resume_id) | (Project.resume_id.is_(None))
        )
    projects_result = await db.execute(projects_query.order_by(Project.created_at.desc()))
    projects = list(projects_result.scalars().all())

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    github_username = user.github_username if user else None

    skill_rows = await db.execute(
        select(ProjectSkill.project_id, Skill.name, Skill.canonical_name)
        .join(Skill, ProjectSkill.skill_id == Skill.id)
        .where(ProjectSkill.project_id.in_([p.id for p in projects]))
    ) if projects else None
    skills_by_project: dict = {}
    all_skill_canonicals: set[str] = set()
    if skill_rows is not None:
        for project_id, name, canonical in skill_rows.all():
            skills_by_project.setdefault(project_id, []).append({"name": name, "canonical": canonical})
            all_skill_canonicals.add(canonical)

    capability_rows = await db.execute(
        select(ProjectCapability.project_id, Capability.name)
        .join(Capability, ProjectCapability.capability_id == Capability.id)
        .where(ProjectCapability.project_id.in_([p.id for p in projects]))
    ) if projects else None
    capabilities_by_project: dict = {}
    all_capability_names: set[str] = set()
    if capability_rows is not None:
        for project_id, name in capability_rows.all():
            capabilities_by_project.setdefault(project_id, []).append(name)
            all_capability_names.add(name)

    analysis_rows = await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)
    )
    all_analysis = list(analysis_rows.scalars().all())

    connected_repos_result = await db.execute(
        select(func.count(func.distinct(GithubSnapshot.repo_name))).where(GithubSnapshot.user_id == user_id)
    )
    connected_repositories = connected_repos_result.scalar_one() or 0

    # ── Fuzzy-match each resume project to at most one repo, and track
    # which repos got claimed so the leftover pass below never repeats one. ──
    matched_repo_names: set[str] = set()
    cards: list[ProjectCard] = []

    for p in projects:
        project_skills = skills_by_project.get(p.id, [])
        project_capabilities = capabilities_by_project.get(p.id, [])

        matched_analysis = None
        for a in all_analysis:
            if a.repo_name.lower() in matched_repo_names:
                continue
            if _names_match(p.name, a.repo_name, p.repo_url):
                matched_analysis = a
                matched_repo_names.add(a.repo_name.lower())
                break

        cards.append(_card_from_resume_project(p, project_skills, project_capabilities, matched_analysis))

    # ── Every synced repo not claimed above becomes its own card, so
    # `sync now` results are never silently dropped just because they
    # weren't also listed on the resume. Non-contributed forks are
    # excluded — they're not this person's original work. ──
    for a in all_analysis:
        if a.repo_name.lower() in matched_repo_names:
            continue
        if a.tier == "fork":
            continue
        cards.append(_card_from_github_only(a, github_username))
        matched_repo_names.add(a.repo_name.lower())

    if not cards:
        return ProjectsOverviewResponse(stats=ProjectsStats(), projects=[])

    # Feature the top-rated projects (up to 4) — computed by rank rather than
    # a stored flag, so "Featured" stays honest as new evidence comes in
    # instead of drifting out of date like a manually-set flag would.
    featured_count = min(4, len(cards))
    ranked = sorted(cards, key=lambda c: c.rating, reverse=True)
    featured_ids = {c.id for c in ranked[:featured_count] if c.rating >= 3.0}
    for c in cards:
        c.is_featured = c.id in featured_ids

    cards.sort(key=lambda c: c.updated_at or c.updated_at, reverse=True)

    resume_backed = sum(1 for p in projects if p.resume_id is not None)
    github_backed = sum(1 for c in cards if c.has_repo)
    flagship_count = sum(1 for c in cards if c.tier == "Flagship Project")

    stats = ProjectsStats(
        total=len(cards),
        flagship=flagship_count,
        technologies=len(all_skill_canonicals | {t for a in all_analysis for t in (a.technologies or [])}),
        resume_coverage_pct=round((resume_backed / len(cards)) * 100) if cards else 0.0,
        github_coverage_pct=round((github_backed / len(cards)) * 100) if cards else 0.0,
        capabilities=len(all_capability_names),
        connected_repositories=connected_repositories,
    )

    return ProjectsOverviewResponse(stats=stats, projects=cards)