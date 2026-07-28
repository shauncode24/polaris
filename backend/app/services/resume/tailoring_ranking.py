"""Deterministic relevance ranking of a candidate's real projects/
experiences against a specific job description's canonical skill
requirements. This is the pre-filter the LLM reasons over — it never
scores relevance itself, same pattern as gap_analysis.py handing the
LLM a deterministic missing-skill list instead of asking it to decide
what's missing.
"""

TYPE_WEIGHTS = {"required": 1.0, "implicit": 0.7, "nice_to_have": 0.3}


def rank_items_for_jd(
    items: list[dict],  # [{"id", "type", "label", "canonical_stack": [...]}]
    canonical_skills: dict[str, str],  # canonical -> "required"|"implicit"|"nice_to_have"
) -> list[dict]:
    ranked = []
    for item in items:
        matched = [s for s in item.get("canonical_stack", []) if s in canonical_skills]
        score = sum(TYPE_WEIGHTS.get(canonical_skills[s], 0.3) for s in matched)
        ranked.append({
            "id": item["id"], "type": item["type"], "label": item["label"],
            "relevance_score": round(score, 2), "matched_skills": sorted(set(matched)),
        })
    return sorted(ranked, key=lambda r: r["relevance_score"], reverse=True)