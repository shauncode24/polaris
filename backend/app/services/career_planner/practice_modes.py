"""Decides HOW a skill should be practiced, so the LLM never proposes
something nonsensical like 'Solve React LeetCode problems' — there is no
such thing, LeetCode is DSA/algorithms only. Every skill canonical name
maps to exactly one practice_mode. The prompt is instructed to only use
LeetCode-style tasks for topics sourced from leetcode_blind_spots /
leetcode_topic_mastery — never for anything in this map.

Hardcoded, not LLM-derived — same philosophy as skill_categories.py's
CATEGORY_MAP and github_taxonomy.py's TECH_CATEGORIES.
"""

FRAMEWORK_UI_SKILLS = {"react", "vue", "angular", "threejs", "javascript", "typescript"}
BACKEND_API_SKILLS = {
    "fastapi", "django", "flask", "express", "nodejs", "aspnet_core",
    "csharp", "ef_core", "rest_api", "graphql", "grpc",
}
INFRA_SKILLS = {"docker", "kubernetes", "terraform"}
DATA_SKILLS = {"postgres", "sql_server", "mongodb", "redis", "vector_search"}
AI_SKILLS = {"langgraph", "langchain", "rag", "openai", "tensorflow", "pytorch"}
LANGUAGE_SKILLS = {"python", "csharp"}

MODE_MAP: dict[str, str] = {
    **{s: "project_build" for s in FRAMEWORK_UI_SKILLS},
    **{s: "project_build" for s in BACKEND_API_SKILLS},
    **{s: "project_build" for s in INFRA_SKILLS},
    **{s: "project_build" for s in DATA_SKILLS},
    **{s: "reading_and_build" for s in AI_SKILLS},
    **{s: "reading" for s in LANGUAGE_SKILLS},
}
DEFAULT_MODE = "project_build"


def get_practice_mode(canonical_skill: str) -> str:
    """Returns one of: 'project_build', 'reading_and_build', 'reading'.

    Deliberately never returns anything DSA/LeetCode-shaped — DSA topics
    come from leetcode_blind_spots/topic_mastery, which already carry
    their own LeetCode-appropriate context. This function's whole job is
    to make sure resume/GitHub-derived *skills* never get a LeetCode task.
    """
    return MODE_MAP.get(canonical_skill, DEFAULT_MODE)