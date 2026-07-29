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
    "fork": "Fork (No Contribution)",
}


def compute_tier(rating: float, has_repo: bool, github_tier: str | None) -> str:
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