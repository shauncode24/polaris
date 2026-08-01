"""Signal-dilution detection — deterministic ranking of bullets against
each other, so review output can say "these bullets are crowding out
your strongest work" instead of only grading each bullet in isolation.
No LLM call: strength is already a real, computed number per bullet
(bullet_strength.py); this module just orders and thresholds it.
"""

WEAK_THRESHOLD = 40  # absolute ceiling — never treat a bullet above this as "weak"
WEAK_PERCENTILE = 0.25  # bottom quartile of THIS resume's own bullets
MAX_STRONG_PER_SOURCE = 4
TOP_OVERALL_COUNT = 8


def detect_dilution(bullets: list[dict]) -> dict:
    """`bullets`: [{"bullet_id", "source_label", "source_type", "text",
    "strength": {...from compute_bullet_strength...}}, ...]
    """
    if not bullets:
        return {"weak_bullets": [], "excess_bullets": [], "strongest_bullets": [], "recommendation": ""}

    ranked = sorted(bullets, key=lambda b: b["strength"]["score"], reverse=True)

    scores = sorted(b["strength"]["score"] for b in ranked)
    percentile_idx = max(0, int(len(scores) * WEAK_PERCENTILE) - 1)
    relative_weak_threshold = min(WEAK_THRESHOLD, scores[percentile_idx]) if scores else WEAK_THRESHOLD

    weak_bullets = [
        {"bullet_id": b["bullet_id"], "source_label": b["source_label"], "score": b["strength"]["score"]}
        for b in ranked if b["strength"]["score"] < relative_weak_threshold
    ]

    by_source: dict[str, list[dict]] = {}
    for b in ranked:
        by_source.setdefault(b["source_label"], []).append(b)

    excess_bullets = []
    for source_label, group in by_source.items():
        group_sorted = sorted(group, key=lambda b: b["strength"]["score"], reverse=True)
        for b in group_sorted[MAX_STRONG_PER_SOURCE:]:
            excess_bullets.append({
                "bullet_id": b["bullet_id"],
                "source_label": source_label,
                "score": b["strength"]["score"],
                "reason": f"{source_label} already has {MAX_STRONG_PER_SOURCE} stronger bullets ahead of this one.",
            })

    strongest_bullets = [
        {"bullet_id": b["bullet_id"], "source_label": b["source_label"], "score": b["strength"]["score"]}
        for b in ranked[:TOP_OVERALL_COUNT]
    ]

    flagged_ids = {b["bullet_id"] for b in weak_bullets} | {b["bullet_id"] for b in excess_bullets}
    if flagged_ids:
        recommendation = (
            f"{len(flagged_ids)} of {len(bullets)} bullets are weak or redundant relative to your "
            f"strongest work and are likely diluting attention from it — consider cutting or tightening them."
        )
    else:
        recommendation = "No significant dilution detected — your bullets are reasonably balanced in strength."

    return {
        "weak_bullets": weak_bullets,
        "excess_bullets": excess_bullets,
        "strongest_bullets": strongest_bullets,
        "recommendation": recommendation,
    }