"""Maps raw GitHub language names and repo topics to career-relevant
categories — turns 'React: 8, FastAPI: 1' into something a Career
Planner can act on ('frontend-heavy, backend-light').

Hardcoded dict, not an LLM call — same reasoning as skill_classifier.py's
tier-1 CANONICAL_SKILLS: cheap, instant, covers the overwhelming
majority of real repo tags. Extend by hand as new topics show up
uncategorized (see the [TRACING] log line below).
"""

TECH_CATEGORIES: dict[str, str] = {
    # languages (from GitHub's language-bytes stats)
    "python": "languages", "javascript": "languages", "typescript": "languages",
    "java": "languages", "c#": "languages", "go": "languages", "rust": "languages",
    "html": "languages", "css": "languages", "c++": "languages", "c": "languages",
    "kotlin": "languages", "swift": "languages", "php": "languages", "ruby": "languages",

    # frontend (from repo topics)
    "react": "frontend", "reactjs": "frontend", "vue": "frontend", "vuejs": "frontend",
    "angular": "frontend", "svelte": "frontend", "nextjs": "frontend", "next-js": "frontend",
    "tailwind": "frontend", "tailwindcss": "frontend", "redux": "frontend", "vite": "frontend",

    # backend
    "fastapi": "backend", "django": "backend", "flask": "backend", "express": "backend",
    "expressjs": "backend", "nodejs": "backend", "aspnet-core": "backend", "aspnetcore": "backend",
    "spring": "backend", "spring-boot": "backend", "graphql": "backend", "grpc": "backend",

    # databases
    "postgresql": "databases", "postgres": "databases", "mongodb": "databases", "mongo": "databases",
    "mysql": "databases", "redis": "databases", "sqlite": "databases", "sql-server": "databases",
    "pgvector": "databases", "dynamodb": "databases",

    # devops
    "docker": "devops", "docker-compose": "devops", "kubernetes": "devops", "k8s": "devops",
    "terraform": "devops", "github-actions": "devops", "ci-cd": "devops", "cicd": "devops",
    "nginx": "devops", "aws": "devops", "azure": "devops", "gcp": "devops",

    # ai / ml
    "langchain": "ai", "langgraph": "ai", "tensorflow": "ai", "pytorch": "ai",
    "openai": "ai", "huggingface": "ai", "llm": "ai", "machine-learning": "ai",
    "nlp": "ai", "rag": "ai", "vector-search": "ai", "finbert": "ai",

    # mobile
    "react-native": "mobile", "flutter": "mobile", "android": "mobile", "ios": "mobile",

    # testing
    "pytest": "testing", "jest": "testing", "testing": "testing", "unit-testing": "testing",
}

# Shared architecture-depth-label -> point mapping (0-100), used by BOTH the
# portfolio-wide maturity rollup (github_insights.build_architecture_maturity_rollup)
# and the per-technology depth score (github_skill_depth.compute_technology_depth).
# Previously these were two separately-tuned dicts for the same four labels
# (0/33/67/100 vs 10/40/75/100) — a repo's architecture read could silently
# score differently depending on which rollup read it. One shared table now.
ARCHITECTURE_DEPTH_POINTS: dict[str, int] = {
    "flat_script": 0,
    "basic_structure": 33,
    "layered": 67,
    "well_architected": 100,
}

# Display-name normalization for technologies detected via language/topic
# scanning (github_analyzer._scan_topics_and_languages), so breadth-based
# detection (this file) and manifest-based detection (github_analyzer.py's
# PACKAGE_JSON_SIGNATURES/REQUIREMENTS_SIGNATURES) speak the same vocabulary
# instead of silently disagreeing on what a repo "uses".
TECH_DISPLAY_NAMES: dict[str, str] = {
    "docker": "Docker", "docker-compose": "Docker Compose",
    "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "terraform": "Terraform", "redis": "Redis",
    "mongodb": "MongoDB", "mongo": "MongoDB",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mysql": "MySQL",
    "pgvector": "pgvector", "sqlite": "SQLite", "dynamodb": "DynamoDB",
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask",
    "express": "Express", "expressjs": "Express", "nodejs": "Node.js",
    "aspnet-core": "ASP.NET Core", "aspnetcore": "ASP.NET Core",
    "spring": "Spring", "spring-boot": "Spring Boot",
    "react": "React", "reactjs": "React", "vue": "Vue", "vuejs": "Vue",
    "angular": "Angular", "svelte": "Svelte",
    "nextjs": "Next.js", "next-js": "Next.js",
    "tailwind": "TailwindCSS", "tailwindcss": "TailwindCSS",
    "redux": "Redux", "vite": "Vite",
    "graphql": "GraphQL", "grpc": "gRPC",
    "pytest": "Testing", "jest": "Testing", "unit-testing": "Testing",
    "github-actions": "CI/CD", "ci-cd": "CI/CD", "cicd": "CI/CD",
    "nginx": "Nginx", "aws": "AWS", "azure": "Azure", "gcp": "GCP",
    "langchain": "LangChain", "langgraph": "LangGraph", "openai": "OpenAI",
    "huggingface": "Hugging Face", "tensorflow": "TensorFlow", "pytorch": "PyTorch",
    "llm": "LLM", "nlp": "NLP", "rag": "RAG", "vector-search": "Vector Search",
    "react-native": "React Native", "flutter": "Flutter",
}

def categorize_technologies(
    repo_language_map: dict[str, dict], repo_topics_map: dict[str, list[str]]
) -> dict[str, dict[str, int]]:
    """Returns {category: {tech_name: repo_count}}. Repo count, not byte
    count — 'used in 8 repos' communicates breadth better for a
    career-facing view than raw bytes, where one generated file can
    dominate a repo's language stats.
    """
    result: dict[str, dict[str, int]] = {}
    uncategorized: set[str] = set()

    def _bump(display_name: str, key: str) -> None:
        category = TECH_CATEGORIES.get(key)
        if category is None:
            uncategorized.add(display_name)
            return
        result.setdefault(category, {})
        result[category][display_name] = result[category].get(display_name, 0) + 1

    for languages in repo_language_map.values():
        for lang in languages:
            _bump(lang, lang.lower())

    for topics in repo_topics_map.values():
        for topic in topics:
            _bump(topic, topic.lower())

    if uncategorized:
        print(f"[TRACING] Uncategorized tech topics — add to TECH_CATEGORIES: {sorted(uncategorized)}", flush=True)

    return result