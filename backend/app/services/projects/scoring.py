"""Rule-based project scoring — same philosophy as resume/confidence.py
and github/github_scoring.py: deterministic and explainable.
"""

AI_SKILLS = {"langgraph", "langchain", "rag", "openai", "tensorflow", "pytorch", "vector_search"}
BACKEND_SKILLS = {
    "fastapi", "django", "flask", "express", "nodejs", "aspnet_core",
    "csharp", "rest_api", "graphql", "grpc", "ef_core",
}

MIN_RATING = 1.0
MAX_RATING = 5.0

# Deterministic keyword -> capability label. Same idea as github_analyzer.py's
# CAPABILITY_MAP, but applied directly to a project's stack so resume-only
# projects (no linked GitHub repo) still get real engineering tags instead
# of a raw tech dump. Never LLM-derived, never guessed.
STACK_CAPABILITY_MAP: dict[str, str] = {
    "docker": "Containerization", "kubernetes": "Containerization",
    "fastapi": "API Design", "django": "API Design", "flask": "API Design",
    "express": "API Design", "nodejs": "API Design", "aspnet_core": "API Design",
    "graphql": "API Design", "rest_api": "API Design",
    "redis": "Caching",
    "postgres": "Database Design", "sql_server": "Database Design",
    "mongodb": "Database Design", "ef_core": "Database Design",
    "langchain": "AI Integration", "langgraph": "AI Integration",
    "openai": "AI Integration", "rag": "AI Integration",
    "vector_search": "AI Integration", "tensorflow": "AI Integration", "pytorch": "AI Integration",
    "jwt": "Authentication", "oauth": "Authentication",
    "pytest": "Testing", "jest": "Testing", "testing": "Testing",
    "kafka": "Distributed Systems", "grpc": "Distributed Systems", "rabbitmq": "Distributed Systems",
    "websocket": "Real-Time Systems", "socketio": "Real-Time Systems",
    "terraform": "DevOps", "cicd": "DevOps", "github_actions": "DevOps",
}


def derive_engineering_tags(stack: list[str], extra_capabilities: list[str] | None = None) -> list[str]:
    """Deterministic. Merges any capabilities already computed elsewhere
    (e.g. GithubProjectAnalysis.capabilities, or a manually-tagged
    ProjectCapability row) with keyword-derived tags from the stack, so
    a project reads as 'Authentication, Caching, AI Integration' instead
    of 'React, Express, MongoDB'. Capped so the UI stays scannable.
    """
    tags: list[str] = list(dict.fromkeys(extra_capabilities or []))
    for tech in stack:
        key = tech.lower().replace(" ", "_").replace(".", "")
        tag = STACK_CAPABILITY_MAP.get(key)
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:5]


_GITHUB_TIER_LABELS = {
    "flagship": "Flagship Project",
    "career": "Career Project",
    "experiment": "Learning Project",
    "archived": "Archived",
}


def compute_tier(rating: float, has_repo: bool, github_tier: str | None) -> str:
    """Replaces the star rating with a label a recruiter can act on.
    Prefers the real GitHub-derived tier (github_analyzer.py already
    computes this from README/tests/CI/activity) when a repo is linked;
    falls back to a rating-based bucket for resume-only projects.
    """
    if github_tier:
        return _GITHUB_TIER_LABELS.get(github_tier, "Career Project")
    if rating >= 4.0 and has_repo:
        return "Flagship Project"
    if rating >= 3.0:
        return "Career Project"
    if rating >= 2.0:
        return "Learning Project"
    return "Prototype"


def compute_rating(
    *,
    description_length: int,
    skill_count: int,
    capability_count: int,
    github_quality_score: float | None,
    github_activity_score: float | None,
) -> float:
    rating = 2.5
    if description_length > 100:
        rating += 0.5
    if skill_count >= 4:
        rating += 0.5
    if capability_count >= 3:
        rating += 0.5
    if github_quality_score is not None:
        rating += (github_quality_score / 100) * 0.75
    if github_activity_score is not None:
        rating += (github_activity_score / 100) * 0.25

    rating = max(MIN_RATING, min(MAX_RATING, rating))
    return round(rating * 2) / 2


def compute_status(github_is_active: bool | None) -> str:
    return "ongoing" if github_is_active else "completed"