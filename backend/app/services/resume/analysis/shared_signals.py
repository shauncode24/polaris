"""Canonical, single-source detectors shared across every resume
analysis module. Before this file existed, metric detection, strong-verb
detection, and tech-keyword detection were each independently
re-implemented in bullet_analysis.py, analysis/content.py,
analysis/metrics.py, analysis/bullet_strength.py, and
ats_scorer_v2.py — meaning "does this bullet have a metric" could
legitimately return different answers depending on which module asked.

This module is the fix: ONE metric pattern, ONE strong-verb vocabulary,
ONE tech-keyword vocabulary. Every consumer imports from here. Extend
these sets by hand, in one place, when new signal is needed.
"""
import re

# --- Metric detection -------------------------------------------------
# Matches: 35%, 3.5%, $50, $1.2M, $500k, 10k, 5M, 3x, 15,000, 150+
METRIC_PATTERN = re.compile(
    r"(\b\d+(\.\d+)?\s*%"
    r"|\$\s?\d[\d,\.]*[kKmMbB]?"
    r"|\b\d[\d,\.]*[kKmMbBxX]\b"
    r"|\b\d{2,}(?:,\d{3})*\b"
    r"|\b\d+\+)"
)


def has_metric(text: str) -> bool:
    return bool(METRIC_PATTERN.search(text))


# --- Strong action verbs ------------------------------------------------
STRONG_ACTION_VERBS: frozenset[str] = frozenset({
    "accelerated", "achieved", "analyzed", "architected", "automated", "built",
    "collaborated", "configured", "consolidated", "contributed", "coordinated",
    "created", "debugged", "decreased", "delivered", "deployed", "designed",
    "developed", "directed", "documented", "drove", "eliminated", "engineered",
    "enhanced", "established", "executed", "expanded", "generated", "implemented",
    "improved", "increased", "initiated", "integrated", "introduced", "investigated",
    "launched", "led", "maintained", "managed", "mentored", "migrated",
    "optimized", "orchestrated", "overhauled", "pioneered", "planned", "published",
    "rebuilt", "redesigned", "reduced", "refactored", "released", "resolved",
    "restructured", "revamped", "reviewed", "saved", "scaled", "shipped",
    "spearheaded", "streamlined", "tested", "trained", "transformed", "wrote",
})

_FIRST_WORD_RE = re.compile(r"^([A-Za-z]+)")


def opens_with_strong_verb(text: str) -> bool:
    m = _FIRST_WORD_RE.match(text.strip())
    if not m:
        return False
    return m.group(1).lower() in STRONG_ACTION_VERBS


# --- Filler / vague phrases ---------------------------------------------
FILLER_PHRASES: tuple[str, ...] = (
    "various", "multiple", "several", "many", "a lot of",
    "team player", "go-getter", "self-starter", "dynamic", "synergy",
    "passionate about", "hardworking", "detail-oriented", "results-driven",
    "fast learner", "quick learner", "out-of-the-box", "thought leader",
)


def has_filler(text: str) -> bool:
    lowered = text.lower()
    return any(f in lowered for f in FILLER_PHRASES)


# --- Tech / keyword vocabulary -------------------------------------------
# Single canonical pool. analysis/keywords.py's DEFAULT_SW_KEYWORDS and
# ats_scorer_v2.py's TECH_KEYWORDS used to be two separately hand-maintained
# sets that could silently drift apart — this is the merged union, used by
# both now.
TECH_KEYWORD_POOL: frozenset[str] = frozenset({
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "bash",
    "react", "vue", "angular", "html", "css", "next.js", "webpack", "vite",
    "tailwind",
    "node.js", "django", "fastapi", "flask", "express", "spring", "rails",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "cassandra", "sqlite", "dynamodb",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform",
    "github actions", "jenkins", "ci/cd", "linux", "ansible",
    "rest api", "graphql", "grpc", "microservices", "unit testing", "tdd", "agile",
    "git", "system design", "performance optimization", "authentication",
    "machine learning", "deep learning", "nlp", "data structures", "algorithms",
    "pytorch", "tensorflow", "scikit-learn",
    "api", "database design", "security", "version control",
})