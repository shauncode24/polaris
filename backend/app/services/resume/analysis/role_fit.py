# backend/app/services/resume/analysis/role_fit.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.jobs.skill_categories import CATEGORY_MAP

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


def compute_role_fit(evidence_skills: list[dict]) -> list[dict]:
    covered_categories = set()
    for s in evidence_skills:
        if s.get("confidence") == "low":
            continue
        # Check canonical first, then fall back to name
        key = s.get("canonical") or s.get("name") or ""
        cat = CATEGORY_MAP.get(key.lower())
        if cat:
            covered_categories.add(cat)
            
    results = []
    for role, needed in ROLE_ARCHETYPES.items():
        overlap = len(needed & covered_categories)
        pct = round((overlap / len(needed)) * 100)
        results.append({"role": role, "match_pct": pct})
        
    return sorted(results, key=lambda r: r["match_pct"], reverse=True)


async def get_confident_canonical_skills(db: AsyncSession) -> list[dict]:
    """Retrieves all skill confidence scores from the database and maps them
    to structured dictionaries with confidence levels (high, medium, low).
    """
    from app.services.evidence import get_all_skill_confidences
    confidences = await get_all_skill_confidences(db)
    
    confident_skills = []
    for canonical, score in confidences.items():
        if score >= 0.5:
            conf_label = "high"
        elif score >= 0.15:
            conf_label = "medium"
        else:
            conf_label = "low"
            
        confident_skills.append({
            "canonical": canonical,
            "name": canonical,
            "confidence": conf_label,
            "score": score
        })
    return confident_skills


def compute_combined_role_fit(confident_skills: list[dict]) -> list[dict]:
    """Wrapper around compute_role_fit that takes mapped confident skills."""
    return compute_role_fit(confident_skills)
