"""Module 6 — Keyword Analyzer.

Compares the resume text against a curated software-engineering keyword
list (when no JD is provided) or against extracted JD requirements.
Deterministic; zero LLM calls.
"""
import re

# ── Default keyword pool (general software engineering) ─────────────────────
DEFAULT_SW_KEYWORDS: frozenset[str] = frozenset({
    # Programming languages
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "bash",
    # Frontend
    "react", "vue", "angular", "html", "css", "next.js", "webpack", "vite",
    # Backend frameworks
    "node.js", "django", "fastapi", "flask", "express", "spring", "rails",
    # Databases
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "cassandra", "sqlite", "dynamodb",
    # Cloud & DevOps
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform",
    "github actions", "jenkins", "ci/cd", "linux",
    # Practices
    "rest api", "graphql", "microservices", "unit testing", "tdd", "agile",
    "git", "system design", "performance optimization", "authentication",
    # Data / AI
    "machine learning", "deep learning", "nlp", "data structures", "algorithms",
    # General
    "api", "database design", "security", "version control",
})


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _keyword_present(kw: str, norm_text: str) -> bool:
    """Word-boundary–aware search so 'sql' doesn't match inside 'nosql'."""
    escaped = re.escape(kw)
    return bool(re.search(r"(?<![a-zA-Z0-9#\+])" + escaped + r"(?![a-zA-Z0-9#\+])", norm_text))


def analyze_keywords(
    raw_text: str,
    jd_keywords: set[str] | None = None,
    profile_keywords: set[str] | None = None,
) -> dict:
    norm_text    = _normalize(raw_text)
    
    if jd_keywords:
        keyword_pool = jd_keywords
    elif profile_keywords:
        keyword_pool = {k.lower() for k in profile_keywords if k}
    else:
        keyword_pool = DEFAULT_SW_KEYWORDS

    matched: list[str] = []
    missing: list[str] = []

    for kw in sorted(keyword_pool):
        if _keyword_present(kw, norm_text):
            matched.append(kw)
        else:
            missing.append(kw)

    total    = len(keyword_pool)
    coverage = len(matched) / total * 100 if total else 0

    # Scale score: 80%+ coverage → 100; linear below.
    score = min(100, round(coverage * 1.25))

    return {
        "score": score,
        "matched": matched,
        "missing": missing[:20],          # top 20 missing for UI
        "matched_count": len(matched),
        "missing_count": len(missing),
        "total_keywords": total,
        "coverage_pct": round(coverage),
        "using_default": jd_keywords is None,
    }
