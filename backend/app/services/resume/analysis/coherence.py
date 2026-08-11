"""Narrative coherence — deterministic layer. Answers "what role does
this resume currently argue for" by aggregating confidence-weighted
skill signal into categories (skill_categories.CATEGORY_MAP), independent
of whether each individual bullet is well-written. This is the fact
base handed to the LLM narrative layer — the LLM never decides the
category distribution itself, only interprets it.
"""
from app.services.taxonomy.skill_taxonomy import CATEGORY_MAP, DEFAULT_CATEGORY
from app.services.resume.analysis.role_fit import ROLE_ARCHETYPES

# Free-text phrasing -> archetype. A target role typed by the user
# ("full stack developer", "back-end engineer", "AI engineer") almost
# never matches a ROLE_ARCHETYPES key verbatim. Previously any non-exact
# match silently fell through to `dominant_category` alone — which is
# what made a stated "Full Stack Developer" target collapse into
# whatever category happened to hold the most skill signal (e.g.
# "General Technical"). This keyword layer catches the common phrasings
# before falling back to that behavior.
ROLE_KEYWORDS: dict[str, str] = {
    "full stack": "Full Stack Engineer",
    "full-stack": "Full Stack Engineer",
    "fullstack": "Full Stack Engineer",
    "backend": "Backend Engineer",
    "back-end": "Backend Engineer",
    "back end": "Backend Engineer",
    "server-side": "Backend Engineer",
    "frontend": "Frontend Engineer",
    "front-end": "Frontend Engineer",
    "front end": "Frontend Engineer",
    "ui engineer": "Frontend Engineer",
    "machine learning": "AI/ML Engineer",
    "ml engineer": "AI/ML Engineer",
    "ai engineer": "AI/ML Engineer",
    "artificial intelligence": "AI/ML Engineer",
    "devops": "DevOps / Platform",
    "platform engineer": "DevOps / Platform",
    "site reliability": "DevOps / Platform",
    "sre": "DevOps / Platform",
}


def compute_category_distribution(skill_confidence_by_canonical: dict[str, float]) -> dict[str, float]:
    """category -> confidence-weighted share of total signal, normalized
    to 0-100. A skill not in CATEGORY_MAP falls into DEFAULT_CATEGORY
    rather than being silently dropped.
    """
    totals: dict[str, float] = {}
    for canonical, confidence in skill_confidence_by_canonical.items():
        category = CATEGORY_MAP.get(canonical, DEFAULT_CATEGORY)
        totals[category] = totals.get(category, 0.0) + confidence

    grand_total = sum(totals.values())
    if grand_total == 0:
        return {}
    return {cat: round((val / grand_total) * 100, 1) for cat, val in totals.items()}


def _categories_for_role(role_label: str | None) -> set[str] | None:
    if not role_label:
        return None
    lowered = role_label.strip().lower()

    # 1. Exact archetype match (role_label literally equals an archetype name)
    for archetype, categories in ROLE_ARCHETYPES.items():
        if archetype.lower() == lowered:
            return categories

    # 2. Fuzzy keyword match against common free-text phrasings
    matched_archetypes: set[str] = set()
    for keyword, archetype in ROLE_KEYWORDS.items():
        if keyword in lowered:
            matched_archetypes.add(archetype)

    if not matched_archetypes:
        return None

    categories: set[str] = set()
    for archetype in matched_archetypes:
        categories |= ROLE_ARCHETYPES.get(archetype, set())
    return categories


def compute_narrative_facts(
    skill_confidence_by_canonical: dict[str, float],
    bullets: list[dict],
    target_role: str | None,
) -> dict:
    """`bullets`: [{"bullet_id", "source_label", "canonical_stack": [...]}]
    (canonical_stack, NOT raw text — resolved skill names). Off-narrative
    bullets are ones whose entire canonical_stack maps to categories
    outside both the dominant category and the target role's expected
    categories — real candidates for cutting when tailoring toward a role.
    """
    distribution = compute_category_distribution(skill_confidence_by_canonical)
    dominant_category = max(distribution, key=distribution.get) if distribution else None

    target_categories = _categories_for_role(target_role)
    aligned_categories = set()
    if dominant_category:
        aligned_categories.add(dominant_category)
    if target_categories:
        aligned_categories |= target_categories

    alignment_pct = None
    if target_categories and distribution:
        alignment_pct = round(sum(distribution.get(c, 0.0) for c in target_categories), 1)

    off_narrative_bullets = []
    for b in bullets:
        stack = b.get("canonical_stack") or []
        if not stack:
            continue
        bullet_categories = {CATEGORY_MAP.get(s, DEFAULT_CATEGORY) for s in stack}
        if bullet_categories and not (bullet_categories & aligned_categories):
            off_narrative_bullets.append({
                "bullet_id": b["bullet_id"],
                "source_label": b["source_label"],
                "categories": sorted(bullet_categories),
            })

    return {
        "category_distribution": distribution,
        "dominant_category": dominant_category,
        "target_role": target_role,
        "target_role_categories": sorted(target_categories) if target_categories else [],
        "target_role_alignment_pct": alignment_pct,
        "off_narrative_bullets": off_narrative_bullets,
    }