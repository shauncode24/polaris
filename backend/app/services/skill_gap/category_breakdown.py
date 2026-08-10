# backend/app/services/skill_gap/category_breakdown.py
"""compute_category_breakdown / compute_overall_match — moved from
jobs/skill_categories.py per design doc §5.5. These are genuinely
comparison logic (they consume have/partial/missing against a role's
canonical skills), so they belong to the Comparison Engine — but now
import the shared taxonomy (CATEGORY_MAP, curriculum rank) instead of
owning it.

compute_peer_benchmarks() was removed (Skill Gap Analyzer implementation
plan, Step 5): it was fully implemented but never wired into
SkillGapAnalysisResponse or called from api/jobs.py, and nothing in the
design-doc comments visible in this codebase specifies it as a required
Skill Gap Analyzer output. Per the plan's own default, dead deterministic
code is removed rather than left reachable-but-unused.

projected_percentage and opportunity_narrative removed (Skill Gap scoping
refactor): those implied career-planning promises ("close these gaps and
you'll reach X%") that belong in the Career Planner module, not here.
"""
from app.services.taxonomy.skill_taxonomy import CATEGORY_MAP, DEFAULT_CATEGORY, get_curriculum_rank  # noqa: F401 (get_curriculum_rank kept for taxonomy import consistency)

TYPE_WEIGHTS = {"required": 1.0, "implicit": 0.7, "nice_to_have": 0.3}

_LABEL_THRESHOLDS = [(0.75, "Excellent"), (0.5, "Strong"), (0.3, "Moderate")]


def _label_for_score(score: float) -> str:
    for floor, label in _LABEL_THRESHOLDS:
        if score >= floor:
            return label
    return "Needs Development"


def compute_category_breakdown(have, partial, missing) -> list[dict]:
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

    return {
        "percentage": percentage,
        "label": label,
        "matched_requirements": f"{matched_count} / {total_count}",
        "required_matched": f"{required_matched} / {required_total}",
        "nice_to_have_matched": f"{nice_matched} / {nice_total}",
    }