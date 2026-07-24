# backend/app/services/github_analyzer.py
from datetime import datetime, timezone

# Evidence -> inferred technology. Checked as a case-insensitive substring
# search against manifest file contents, so "fastapi>=0.139" still matches.
PACKAGE_JSON_SIGNATURES = {
    "react": "React", "vue": "Vue", "express": "Express",
    "next": "Next.js", "tailwindcss": "TailwindCSS", "jest": "Testing",
}
REQUIREMENTS_SIGNATURES = {
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask",
    "redis": "Redis", "psycopg": "PostgreSQL", "sqlalchemy": "SQLAlchemy",
    "langchain": "LangChain", "langgraph": "LangGraph", "openai": "OpenAI",
    "pytest": "Testing",
}

# Technology -> capability it demonstrates. Many-to-one: several
# technologies can each independently earn the same capability tag.
CAPABILITY_MAP = {
    "Docker": "Containerization", "Docker Compose": "Containerization",
    "FastAPI": "API Design", "Express": "API Design", "Next.js": "API Design",
    "Django": "API Design", "Flask": "API Design",
    "Redis": "Caching",
    "PostgreSQL": "Database Design", "SQLAlchemy": "Database Design",
    "LangChain": "AI Integration", "LangGraph": "AI Integration", "OpenAI": "AI Integration",
    "CI/CD": "DevOps", "Testing": "Testing",
}

FRONTEND_TECH = {"React", "Vue", "Next.js", "TailwindCSS"}
BACKEND_TECH = {"FastAPI", "Django", "Flask", "Express"}
DATABASE_TECH = {"PostgreSQL", "SQLAlchemy", "Redis"}


def _scan(content: str | None, signatures: dict[str, str]) -> set[str]:
    if not content:
        return set()
    lowered = content.lower()
    return {tech for keyword, tech in signatures.items() if keyword in lowered}


def analyze_repo(
    repo_name: str,
    languages: dict,
    package_json: str | None,
    requirements_txt: str | None,
    pyproject_toml: str | None,
    has_dockerfile: bool,
    has_compose: bool,
    has_workflows: bool,
    has_tests_dir: bool,
    has_readme: bool,
    commits_30d: int,
    last_commit_at: datetime | None,
    is_archived: bool,
) -> dict:
    """Pure derivation — same inputs always produce the same output, so
    this is safe to re-run any time the scoring formula changes, without
    touching github_snapshots at all (§5.5's 'inference is a rebuildable cache').
    """
    technologies: set[str] = set()
    technologies |= _scan(package_json, PACKAGE_JSON_SIGNATURES)
    technologies |= _scan(requirements_txt, REQUIREMENTS_SIGNATURES)
    technologies |= _scan(pyproject_toml, REQUIREMENTS_SIGNATURES)

    if has_dockerfile:
        technologies.add("Docker")
    if has_compose:
        technologies.add("Docker Compose")
    if has_workflows:
        technologies.add("CI/CD")
    if has_tests_dir:
        technologies.add("Testing")

    is_backend = bool(technologies & BACKEND_TECH)
    is_frontend = bool(technologies & FRONTEND_TECH) or any(
        lang in languages for lang in ("JavaScript", "TypeScript", "HTML", "CSS")
    ) and not is_backend is False and bool(technologies & FRONTEND_TECH)
    is_database = bool(technologies & DATABASE_TECH)
    is_containerized = has_dockerfile or has_compose
    has_tests = has_tests_dir or "Testing" in technologies
    has_ci = has_workflows

    if is_backend and is_frontend:
        category = "Full Stack"
    elif is_backend:
        category = "Backend"
    elif is_frontend:
        category = "Frontend"
    else:
        category = "Library/Other"

    capabilities = sorted({CAPABILITY_MAP[t] for t in technologies if t in CAPABILITY_MAP})

    primary_language = max(languages, key=languages.get) if languages else None

    last_activity_days = (
        (datetime.now(timezone.utc) - last_commit_at).days if last_commit_at else None
    )
    is_active = last_activity_days is not None and last_activity_days <= 30

    activity_score = round(min(commits_30d / 20, 1.0) * 100, 1)
    quality_score = round(
        (0.3 * has_readme + 0.4 * has_tests + 0.3 * has_ci) * 100, 1
    )
    maintenance_score = (
        0.0 if is_archived
        else round(max(0, 100 - min(last_activity_days if last_activity_days is not None else 999, 100)), 1)
    )

    return {
        "repo_name": repo_name,
        "category": category,
        "primary_language": primary_language,
        "technologies": sorted(technologies),
        "capabilities": capabilities,
        "is_backend": is_backend,
        "is_frontend": is_frontend,
        "is_database": is_database,
        "is_containerized": is_containerized,
        "has_readme": has_readme,
        "has_tests": has_tests,
        "has_ci": has_ci,
        "is_active": is_active,
        "last_activity_days": last_activity_days,
        "activity_score": activity_score,
        "quality_score": quality_score,
        "maintenance_score": maintenance_score,
    }


def build_portfolio_analysis(
    repo_analyses: list[dict],
    previous_technology_distribution: dict[str, int] | None = None,
) -> dict:
    """Portfolio-wide rollup over every repo's analysis. Also the diffing
    point for trend observations — compares against the *previous* sync's
    technology_distribution if one was passed in.
    """
    active_projects = [r["repo_name"] for r in repo_analyses if r["is_active"]]
    neglected_projects = [
        r["repo_name"] for r in repo_analyses
        if not r["is_active"] and (r["last_activity_days"] or 0) > 60
    ]

    strongest_projects = [
        r["repo_name"] for r in sorted(
            repo_analyses, key=lambda r: r["quality_score"] + r["activity_score"], reverse=True
        )[:5]
    ]
    recently_active_projects = [
        r["repo_name"] for r in sorted(
            repo_analyses, key=lambda r: r["last_activity_days"] if r["last_activity_days"] is not None else 9999
        )[:5]
    ]

    technology_distribution: dict[str, int] = {}
    for r in repo_analyses:
        for tech in r["technologies"]:
            technology_distribution[tech] = technology_distribution.get(tech, 0) + 1

    quality_metrics = {
        "total_repos": len(repo_analyses),
        "repos_with_tests": sum(1 for r in repo_analyses if r["has_tests"]),
        "repos_with_ci": sum(1 for r in repo_analyses if r["has_ci"]),
        "repos_without_readme": sum(1 for r in repo_analyses if not r["has_readme"]),
        "containerized_repos": sum(1 for r in repo_analyses if r["is_containerized"]),
        "full_stack_repos": sum(1 for r in repo_analyses if r["category"] == "Full Stack"),
    }

    observations: list[str] = []
    if recently_active_projects:
        observations.append(f"{recently_active_projects[0]} is your most recently active project.")
    if neglected_projects:
        names = ", ".join(neglected_projects[:3])
        observations.append(f"No recent activity on: {names}.")
    if quality_metrics["repos_without_readme"] > 0:
        observations.append(
            f"{quality_metrics['repos_without_readme']} of {quality_metrics['total_repos']} "
            f"repositories still don't have a README."
        )
    if quality_metrics["repos_with_tests"] < quality_metrics["total_repos"] / 2:
        observations.append(
            f"Only {quality_metrics['repos_with_tests']} of {quality_metrics['total_repos']} "
            f"repositories contain automated tests."
        )
    if previous_technology_distribution:
        for tech, count in technology_distribution.items():
            prev = previous_technology_distribution.get(tech, 0)
            if count > prev:
                observations.append(f"{tech} usage increased since your last sync ({prev} → {count} repos).")

    return {
        "active_projects": active_projects,
        "neglected_projects": neglected_projects,
        "strongest_projects": strongest_projects,
        "recently_active_projects": recently_active_projects,
        "technology_distribution": technology_distribution,
        "quality_metrics": quality_metrics,
        "observations": observations,
    }