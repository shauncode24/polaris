WEIGHTS = {
    "project": 0.35,
    "github": 0.30,
    "experience": 0.25,
    "certificate": 0.15,
    "leetcode_tag": 0.10,
}
CONFIDENCE_CAP = 0.97

STACK_ONLY_MULTIPLIER = 0.55

# Fix #8 (Engineering Identity): previously two stack-only resume
# mentions of e.g. Docker (0.35 x 0.55 twice, discounted) could
# numerically outweigh one deeply-verified GitHub repo (flat 0.30) —
# which inverts the trust ordering you'd actually want, since those two
# mentions are the SAME source type repeated, not independent
# corroboration. This small multiplicative bonus only applies when >= 2
# DISTINCT source TYPES back a skill (e.g. project + github_repo), never
# for repeated evidence from the same type.
CORROBORATION_BONUS_MULTIPLIER = 1.15
MIN_DISTINCT_SOURCE_TYPES_FOR_BONUS = 2


def compute_skill_confidence(evidence_weights: list[float]) -> float:
    return min(sum(evidence_weights), CONFIDENCE_CAP)


def compute_corroboration_count(evidence_rows: list) -> int:
    """Number of DISTINCT source TYPES backing a skill (e.g. project +
    github_repo = 2). This is a DIFFERENT signal from confidence: two
    stack-only resume mentions of the same skill still count as
    corroboration_count=1 (same source type twice), while one project
    mention + one verified GitHub repo counts as 2 — genuinely
    independent, stronger evidence.
    """
    return len({getattr(e, "source_type", None) for e in evidence_rows} - {None})


def compute_decayed_skill_confidence(evidence_rows: list) -> float:
    """Recency-aware version of compute_skill_confidence for callers that
    already have persisted SkillEvidence rows (with a created_at) in
    hand. Also applies the corroboration bonus (fix #8) when >= 2
    distinct source types back the skill.
    """
    from app.services.resume.decay import decay_multiplier
    decayed_weights = [e.weight * decay_multiplier(getattr(e, "created_at", None)) for e in evidence_rows]
    base = compute_skill_confidence(decayed_weights)

    if compute_corroboration_count(evidence_rows) >= MIN_DISTINCT_SOURCE_TYPES_FOR_BONUS:
        base = min(base * CORROBORATION_BONUS_MULTIPLIER, CONFIDENCE_CAP)

    return base