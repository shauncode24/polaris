# backend/app/services/resume/analysis/role_fit.py
from app.services.jobs.skill_categories import CATEGORY_MAP

ROLE_ARCHETYPES = {
    "Backend Engineer": {"Backend Development", "Database & Data"},
    "Frontend Engineer": {"Frontend Development"},
    "Full Stack Engineer": {"Backend Development", "Frontend Development"},
    "AI/ML Engineer": {"AI/ML Engineering"},
    "DevOps / Platform": {"Infrastructure & DevOps"},
}

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
