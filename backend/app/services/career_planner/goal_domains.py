"""Maps a free-text goal title to the skill domains it implies, so the
Career Planner can weight goal-relevant gaps higher than irrelevant ones.
Hand-seeded, same philosophy as skill_categories.py's CATEGORY_MAP —
cheap, deterministic, extend by hand as new goal phrasing shows up.
"""

GOAL_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "ai engineer": [
        "langgraph", "langchain", "rag", "openai", "vector_search",
        "python", "fastapi", "docker", "redis", "postgres",
    ],
    "backend engineer": [
        "python", "fastapi", "django", "flask", "postgres", "redis",
        "docker", "rest_api", "sql_server", "aspnet_core", "csharp", "ef_core",
    ],
    "frontend engineer": [
        "react", "javascript", "typescript", "threejs", "vue", "angular",
    ],
    "full stack engineer": [
        "react", "javascript", "typescript", "python", "fastapi",
        "nodejs", "express", "postgres", "docker",
    ],
    "devops engineer": ["docker", "kubernetes", "terraform"],
    "data engineer": ["python", "postgres", "sql_server", "redis", "vector_search"],
}


def _matching_domains(goal_title: str) -> list[str]:
    lowered = goal_title.lower()
    return [domain for domain in GOAL_DOMAIN_KEYWORDS if domain in lowered]


def goal_relevance_score(canonical_skill: str, goal_title: str) -> float:
    """1.0 if the skill belongs to a domain matched by the goal title,
    else 0.0. Binary, not graded — there's no reliable free signal for
    partial credit without another LLM call, and this has to stay cheap
    and deterministic (§4.3's own philosophy: don't over-engineer this).
    """
    domains = _matching_domains(goal_title)
    if not domains:
        return 0.0
    relevant = {s for d in domains for s in GOAL_DOMAIN_KEYWORDS[d]}
    return 1.0 if canonical_skill in relevant else 0.0