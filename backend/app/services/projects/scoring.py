"""Rule-based project scoring — same philosophy as resume/confidence.py
and github/github_scoring.py: deterministic and explainable, so 'how
strong is this project' and 'is it still active' never require an LLM
call just to render a gallery card.
"""

AI_SKILLS = {"langgraph", "langchain", "rag", "openai", "tensorflow", "pytorch", "vector_search"}
BACKEND_SKILLS = {
    "fastapi", "django", "flask", "express", "nodejs", "aspnet_core",
    "csharp", "rest_api", "graphql", "grpc", "ef_core",
}

MIN_RATING = 1.0
MAX_RATING = 5.0


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
    # Round to the nearest half-star for a clean UI.
    return round(rating * 2) / 2


def compute_status(github_is_active: bool | None) -> str:
    return "ongoing" if github_is_active else "completed"