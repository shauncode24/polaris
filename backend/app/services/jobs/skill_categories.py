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

CURRICULUM_PHASES: dict[str, tuple[str, int]] = {
    "docker": ("Foundation", 1),
    "git": ("Foundation", 1),
    "linux": ("Foundation", 1),

    "python": ("Languages", 2),
    "javascript": ("Languages", 2),
    "typescript": ("Languages", 2),
    "csharp": ("Languages", 2),

    "postgres": ("Databases", 3),
    "sql_server": ("Databases", 3),
    "mongodb": ("Databases", 3),

    "redis": ("Caching", 4),

    "fastapi": ("Advanced APIs", 5),
    "express": ("Advanced APIs", 5),
    "graphql": ("Advanced APIs", 5),
    "rest_api": ("Advanced APIs", 5),
    "django": ("Advanced APIs", 5),
    "flask": ("Advanced APIs", 5),

    "kubernetes": ("Orchestration", 6),
    "terraform": ("Orchestration", 6),

    "langgraph": ("Agent Workflows", 7),
    "rag": ("Agent Workflows", 7),
    "langchain": ("Agent Workflows", 7),
    "openai": ("Agent Workflows", 7),
}


def get_curriculum_phase(skill_name: str) -> str:
    return CURRICULUM_PHASES.get(skill_name, ("General Technical", 8))[0]


def get_curriculum_rank(skill_name: str) -> int:
    return CURRICULUM_PHASES.get(skill_name, ("General Technical", 8))[1]

# A missing "required" skill should hurt the overall score far more than
# a missing "nice_to_have" one — flat averaging would hide that.
TYPE_WEIGHTS = {"required": 1.0, "implicit": 0.7, "nice_to_have": 0.3}

_LABEL_THRESHOLDS = [(0.75, "Excellent"), (0.5, "Strong"), (0.3, "Moderate")]


def _label_for_score(score: float) -> str:
    for floor, label in _LABEL_THRESHOLDS:
        if score >= floor:
            return label
    return "Needs Development"


def compute_category_breakdown(have, partial, missing) -> list[dict]:
    """have/partial/missing are the lists already on SkillGapReport.
    Returns one entry per category that had at least one relevant skill,
    sorted strongest-first so the UI can render it directly.
    """
    cat_have = {}
    cat_partial = {}
    cat_missing = {}

    all_categories = set()
    for h in have:
        cat = CATEGORY_MAP.get(h.skill, DEFAULT_CATEGORY)
        cat_have.setdefault(cat, []).append(h.skill)
        all_categories.add(cat)
    for p in partial:
        cat = CATEGORY_MAP.get(p.skill, DEFAULT_CATEGORY)
        cat_partial.setdefault(cat, []).append(p.skill)
        all_categories.add(cat)
    for m in missing:
        cat = CATEGORY_MAP.get(m.skill, DEFAULT_CATEGORY)
        cat_missing.setdefault(cat, []).append(m.skill)
        all_categories.add(cat)

    breakdown = []
    for cat in all_categories:
        haves = cat_have.get(cat, [])
        partials = cat_partial.get(cat, [])
        missings = cat_missing.get(cat, [])

        total_skills = len(haves) + len(partials) + len(missings)
        matched_count = len(haves) + len(partials)

        h_conf = [h.confidence for h in have if CATEGORY_MAP.get(h.skill, DEFAULT_CATEGORY) == cat]
        p_conf = [p.confidence for p in partial if CATEGORY_MAP.get(p.skill, DEFAULT_CATEGORY) == cat]
        scores = h_conf + p_conf + [0.0] * len(missings)
        avg_score = sum(scores) / len(scores) if scores else 0.0

        breakdown.append({
            "category": cat,
            "label": _label_for_score(avg_score),
            "score": round(avg_score, 2),
            "skill_count": total_skills,
            "matched_skills": f"{matched_count} / {total_skills}",
            "missing_skills": sorted(missings),
        })

    return sorted(breakdown, key=lambda b: b["score"], reverse=True)


def compute_overall_match(canonical_skills: dict[str, str], have, partial, missing) -> dict:
    """canonical_skills: canonical_name -> "required"|"implicit"|"nice_to_have"
    — exactly what api/jobs.py already builds during JD extraction.
    """
    have_by_skill = {h.skill: h.confidence for h in have}
    partial_by_skill = {p.skill: p.confidence for p in partial}
    missing_set = {m.skill for m in missing}

    have_names = set(have_by_skill.keys())
    partial_names = set(partial_by_skill.keys())
    matched_set = have_names | partial_names

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

    total_count = len(canonical_skills)
    matched_count = sum(1 for s in canonical_skills if s in matched_set)

    required_skills_list = [s for s, cat in canonical_skills.items() if cat in ("required", "implicit")]
    required_total = len(required_skills_list)
    required_matched = sum(1 for s in required_skills_list if s in matched_set)

    nice_to_have_list = [s for s, cat in canonical_skills.items() if cat == "nice_to_have"]
    nice_total = len(nice_to_have_list)
    nice_matched = sum(1 for s in nice_to_have_list if s in matched_set)

    # Opportunity score projection (learning the top 3 missing skills)
    missing_by_rank = sorted(list(missing_set), key=get_curriculum_rank)
    top_3_missing = missing_by_rank[:3]

    projected_sum = weighted_sum
    for skill in top_3_missing:
        # Assume learning it/demonstrating practice brings confidence score to 0.9
        projected_sum += 0.9 * TYPE_WEIGHTS.get(canonical_skills.get(skill), 0.5)

    projected_percentage = round((projected_sum / weight_total) * 100, 1) if weight_total > 0 else 0.0

    if len(missing_by_rank) == 0:
        opportunity_narrative = "Your profile is fully aligned with all requirements."
    else:
        top_skills_str = ", ".join(s.title() for s in top_3_missing)
        opportunity_narrative = (
            f"Closing the top missing skill(s) ({top_skills_str}) would increase your estimated "
            f"alignment from {int(percentage)}% to {int(projected_percentage)}%."
        )

    return {
        "percentage": percentage,
        "label": label,
        "matched_requirements": f"{matched_count} / {total_count}",
        "required_matched": f"{required_matched} / {required_total}",
        "nice_to_have_matched": f"{nice_matched} / {nice_total}",
        "projected_percentage": projected_percentage,
        "opportunity_narrative": opportunity_narrative,
    }


def compute_peer_benchmarks(have, partial, missing) -> list[dict]:
    categories_to_check = {
        "Backend Development": "Backend Programming",
        "Infrastructure & DevOps": "Infrastructure",
        "Database & Data": "Databases",
        "AI/ML Engineering": "AI Engineering",
    }

    matched_skills = set(h.skill for h in have) | set(p.skill for p in partial)

    standings = []
    for db_cat, ui_name in categories_to_check.items():
        matched_in_cat = sum(1 for s in matched_skills if CATEGORY_MAP.get(s) == db_cat)

        if matched_in_cat >= 2:
            standing = "Above Average"
        elif matched_in_cat == 1:
            standing = "Average"
        else:
            standing = "Below Average"

        standings.append({
            "area": ui_name,
            "standing": standing,
        })

    return standings