# backend/app/services/resume/analysis/role_fit.py
"""ROLE_ARCHETYPES is the shared vocabulary of role names + their
associated skill categories — used for keyword/category alignment
(resume/analysis/coherence.py's target-role matching). It is NOT used to
compute a role-fit rating anymore.

Role-fit itself is deliberately and entirely LLM-generated — see
services/identity/role_fit.py's module docstring (Engineering Identity
fix #2). There is no deterministic compute_role_fit function in this
codebase anymore; do not add one back here.
"""
from app.services.taxonomy.skill_taxonomy import CATEGORY_MAP

ROLE_ARCHETYPES = {
    "Backend Engineer": {"Backend Development", "Database & Data"},
    "Frontend Engineer": {"Frontend Development"},
    "Full Stack Engineer": {"Backend Development", "Frontend Development"},
    "AI/ML Engineer": {"AI/ML Engineering"},
    "DevOps / Platform": {"Infrastructure & DevOps"},
}

# Guard against the two taxonomies (this one and skill_categories.CATEGORY_MAP)
# silently drifting apart — every category referenced here must exist there.
_VALID_CATEGORIES = set(CATEGORY_MAP.values())
assert all(
    cat in _VALID_CATEGORIES for cats in ROLE_ARCHETYPES.values() for cat in cats
), "ROLE_ARCHETYPES references a category not present in skill_categories.CATEGORY_MAP"