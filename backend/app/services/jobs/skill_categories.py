"""Rule-based category taxonomy + aggregate scoring for the Skill Gap
Analyzer's UI-facing output. Deterministic, same philosophy as
resume/confidence.py and jobs/effort_estimation.py: compute anything
that can be computed reliably in code, and only hand the LLM numbers
that are already true — never let it invent a percentage or a label.
"""

CATEGORY_MAP: dict[str, str] = {
    # Backend Development
    "python": "Backend Development", "fastapi": "Backend Development",
    "django": "Backend Development", "flask": "Backend Development",
    "nodejs": "Backend Development", "express": "Backend Development",
    "aspnet_core": "Backend Development", "csharp": "Backend Development",
    "ef_core": "Backend Development", "rest_api": "Backend Development",
    "graphql": "Backend Development", "grpc": "Backend Development",

    # Frontend Development
    "react": "Frontend Development", "javascript": "Frontend Development",
    "typescript": "Frontend Development", "threejs": "Frontend Development",
    "vue": "Frontend Development", "angular": "Frontend Development",

    # Database & Data
    "postgres": "Database & Data", "sql_server": "Database & Data",
    "mongodb": "Database & Data", "redis": "Database & Data",
    "vector_search": "Database & Data",

    # Infrastructure & DevOps
    "docker": "Infrastructure & DevOps", "kubernetes": "Infrastructure & DevOps",
    "terraform": "Infrastructure & DevOps",

    # AI / ML Engineering
    "langgraph": "AI/ML Engineering", "rag": "AI/ML Engineering",
    "langchain": "AI/ML Engineering", "openai": "AI/ML Engineering",
    "tensorflow": "AI/ML Engineering", "pytorch": "AI/ML Engineering",
}
DEFAULT_CATEGORY = "General Technical"

# A missing "required" skill should hurt the overall score far more than
# a missing "nice_to_have" one — flat averaging would hide that.
TYPE_WEIGHTS = {"required": 1.0, "implicit": 0.7, "nice_to_have": 0.3}

_LABEL_THRESHOLDS = [(0.75, "Excellent"), (0.5, "Strong"), (0.3, "Moderate"), (0.0001, "Weak")]


def _label_for_score(score: float) -> str:
    if score <= 0:
        return "Not Assessed"
    for floor, label in _LABEL_THRESHOLDS:
        if score >= floor:
            return label
    return "Weak"


def compute_category_breakdown(have, partial, missing) -> list[dict]:
    """have/partial/missing are the lists already on SkillGapReport.
    Returns one entry per category that had at least one relevant skill,
    sorted strongest-first so the UI can render it directly.
    """
    buckets: dict[str, list[float]] = {}

    for h in have:
        buckets.setdefault(CATEGORY_MAP.get(h.skill, DEFAULT_CATEGORY), []).append(h.confidence)
    for p in partial:
        buckets.setdefault(CATEGORY_MAP.get(p.skill, DEFAULT_CATEGORY), []).append(p.confidence)
    for m in missing:
        buckets.setdefault(CATEGORY_MAP.get(m.skill, DEFAULT_CATEGORY), []).append(0.0)

    breakdown = [
        {
            "category": cat,
            "label": _label_for_score(sum(scores) / len(scores)),
            "score": round(sum(scores) / len(scores), 2),
            "skill_count": len(scores),
        }
        for cat, scores in buckets.items()
    ]
    return sorted(breakdown, key=lambda b: b["score"], reverse=True)


def compute_overall_match(canonical_skills: dict[str, str], have, partial, missing) -> dict:
    """canonical_skills: canonical_name -> "required"|"implicit"|"nice_to_have"
    — exactly what api/jobs.py already builds during JD extraction.
    """
    have_by_skill = {h.skill: h.confidence for h in have}
    partial_by_skill = {p.skill: p.confidence for p in partial}
    missing_set = {m.skill for m in missing}

    weighted_sum = weight_total = 0.0
    for skill, category in canonical_skills.items():
        weight = TYPE_WEIGHTS.get(category, 0.5)
        if skill in have_by_skill:
            score = have_by_skill[skill]
        elif skill in partial_by_skill:
            score = partial_by_skill[skill]
        elif skill in missing_set:
            score = 0.0
        else:
            continue
        weighted_sum += score * weight
        weight_total += weight

    percentage = round((weighted_sum / weight_total) * 100, 1) if weight_total > 0 else 0.0

    if percentage >= 75:
        label = "Strong Match"
    elif percentage >= 50:
        label = "Good Match"
    elif percentage >= 25:
        label = "Partial Match"
    else:
        label = "Weak Match"

    return {"percentage": percentage, "label": label}