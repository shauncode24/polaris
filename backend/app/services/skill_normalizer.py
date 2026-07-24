CANONICAL_SKILLS: dict[str, str] = {
    "react": "react", "reactjs": "react", "react.js": "react",
    "fastapi": "fastapi",
    "python": "python",
    "docker": "docker",
    "redis": "redis",
    "postgres": "postgres", "postgresql": "postgres",
    "typescript": "typescript",
    "javascript": "javascript", "js": "javascript",
    "sql server": "sql_server",
    "asp.net core": "aspnet_core",
    "c#": "csharp",
    "ef core": "ef_core",
    "langgraph": "langgraph",
    # add to this as real extractions surface new spellings
}


def normalize_skill(raw_name: str) -> str:
    key = raw_name.strip().lower()
    return CANONICAL_SKILLS.get(key, key.replace(" ", "_"))