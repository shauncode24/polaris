"""Narrative coherence — deterministic layer. Answers "what role does
this resume currently argue for" by aggregating confidence-weighted
skill signal into categories (skill_categories.CATEGORY_MAP), independent
of whether each individual bullet is well-written. This is the fact
base handed to the LLM narrative layer — the LLM never decides the
category distribution itself, only interprets it.
"""
from app.services.jobs.skill_categories import CATEGORY_MAP, DEFAULT_CATEGORY
from app.services.resume.analysis.role_fit import ROLE_ARCHETYPES


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
    for archetype, categories in ROLE_ARCHETYPES.items():
        if archetype.lower() == role_label.lower():
            return categories
    return None


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