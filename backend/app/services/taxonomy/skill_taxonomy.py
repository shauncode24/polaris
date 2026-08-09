# backend/app/services/taxonomy/skill_taxonomy.py
"""Shared skill/curriculum taxonomy — moved out of app/services/jobs/
skill_categories.py per the Job Intelligence design doc §2.4, since
Career Planner (career_planner/curriculum.py) already independently
touches curriculum concepts and neither Job Intelligence nor Skill Gap
Analyzer should "own" this vocabulary exclusively.

This is a duplicate of the data in jobs/skill_categories.py during the
transition (that module is left untouched for backward compatibility —
see Phase 5 in the design doc, not yet done). Job Intelligence's
normalization stage and Skill Gap Analyzer's category_breakdown module
both import from HERE going forward; nothing else should.
"""

CATEGORY_MAP: dict[str, str] = {
    "python": "Backend Development", "fastapi": "Backend Development",
    "django": "Backend Development", "flask": "Backend Development",
    "nodejs": "Backend Development", "express": "Backend Development",
    "aspnet_core": "Backend Development", "csharp": "Backend Development",
    "ef_core": "Backend Development", "rest_api": "Backend Development",
    "graphql": "Backend Development", "grpc": "Backend Development",

    "react": "Frontend Development", "javascript": "Frontend Development",
    "typescript": "Frontend Development", "threejs": "Frontend Development",
    "vue": "Frontend Development", "angular": "Frontend Development",

    "postgres": "Database & Data", "sql_server": "Database & Data",
    "mongodb": "Database & Data", "redis": "Database & Data",
    "vector_search": "Database & Data",

    "docker": "Infrastructure & DevOps", "kubernetes": "Infrastructure & DevOps",
    "terraform": "Infrastructure & DevOps",

    "langgraph": "AI/ML Engineering", "rag": "AI/ML Engineering",
    "langchain": "AI/ML Engineering", "openai": "AI/ML Engineering",
    "tensorflow": "AI/ML Engineering", "pytorch": "AI/ML Engineering",
}
DEFAULT_CATEGORY = "General Technical"

CURRICULUM_PHASES: dict[str, tuple[str, int]] = {
    "docker": ("Foundation", 1), "git": ("Foundation", 1), "linux": ("Foundation", 1),

    "python": ("Languages", 2), "javascript": ("Languages", 2),
    "typescript": ("Languages", 2), "csharp": ("Languages", 2),

    "postgres": ("Databases", 3), "sql_server": ("Databases", 3), "mongodb": ("Databases", 3),

    "redis": ("Caching", 4),

    "fastapi": ("Advanced APIs", 5), "express": ("Advanced APIs", 5),
    "graphql": ("Advanced APIs", 5), "rest_api": ("Advanced APIs", 5),
    "django": ("Advanced APIs", 5), "flask": ("Advanced APIs", 5),

    "kubernetes": ("Orchestration", 6), "terraform": ("Orchestration", 6),

    "langgraph": ("Agent Workflows", 7), "rag": ("Agent Workflows", 7),
    "langchain": ("Agent Workflows", 7), "openai": ("Agent Workflows", 7),
}


def get_curriculum_phase(skill_name: str) -> str:
    return CURRICULUM_PHASES.get(skill_name, ("General Technical", 8))[0]


def get_curriculum_rank(skill_name: str) -> int:
    return CURRICULUM_PHASES.get(skill_name, ("General Technical", 8))[1]