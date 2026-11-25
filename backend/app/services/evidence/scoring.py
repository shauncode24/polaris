"""How skill evidence becomes a confidence number and a label.

The single place that owns:
  * the per-source evidence weights and the confidence cap
  * recency decay (older evidence counts for less)
  * the corroboration bonus (independent source types back each other up)
  * the score -> label cutoffs (high / medium / low, and the skill-gap
    have / partial / missing vocabulary built on the same cutoffs)

Nothing else hardcodes a confidence cutoff or weight.
"""
from datetime import datetime, timezone

# ---------------------------------------------------------------- weights
WEIGHTS = {
    "project": 0.35,
    "github": 0.30,
    "experience": 0.25,
    "certificate": 0.15,
    "leetcode_tag": 0.10,
    # Phase 4 — LinkedIn evidence. Deliberately weighted below every
    # other source: a LinkedIn skill mention is self-reported with no
    # deeper corroboration (unlike a project/GitHub repo/experience
    # bullet, which are themselves the evidence). It's real signal, but
    # the weakest kind — same reasoning as leetcode_tag being the
    # lowest of the pre-existing weights.
    "linkedin": 0.20,
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
    decayed_weights = [e.weight * decay_multiplier(getattr(e, "created_at", None)) for e in evidence_rows]
    base = compute_skill_confidence(decayed_weights)

    if compute_corroboration_count(evidence_rows) >= MIN_DISTINCT_SOURCE_TYPES_FOR_BONUS:
        base = min(base * CORROBORATION_BONUS_MULTIPLIER, CONFIDENCE_CAP)

    return base


# ------------------------------------------------------------ recency decay
# Recency decay for skill evidence weight. Before this existed, skill
# confidence only ever grew: a resume bullet from three years ago with zero
# corroborating activity since read as fully confident, forever.
# (days_old_ceiling, weight_multiplier)
DECAY_STEPS: list[tuple[int, float]] = [
    (90, 1.0),   # fresh — full weight
    (180, 0.85),
    (365, 0.65),
    (730, 0.50),  # 1-2 years stale
]
FLOOR_MULTIPLIER = 0.35  # evidence never fully disappears — it was real once,
                          # but past ~2 years it should read as materially
                          # weaker than recent evidence rather than plateauing
                          # at a static floor forever.


def decay_multiplier(created_at: datetime | None) -> float:
    if created_at is None:
        return 1.0  # legacy row with no timestamp — treat as fresh rather than penalize
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    days_old = (datetime.now(timezone.utc) - created_at).days
    for ceiling, multiplier in DECAY_STEPS:
        if days_old <= ceiling:
            return multiplier
    return FLOOR_MULTIPLIER


# ----------------------------------------------------------------- labels
# (floor, label), descending order — label applies once score >= floor.
CONFIDENCE_BUCKETS: list[tuple[float, str]] = [
    (0.6, "high"),
    (0.3, "medium"),
    (0.0, "low"),
]

# Skill-gap vocabulary (have/partial/missing) maps onto the SAME floors
# as CONFIDENCE_BUCKETS — a "high" confidence skill is always a "have"
# skill and a "low" one is always "missing". No separate cutoffs exist
# anywhere else in the codebase after this fix.
GAP_ANALYSIS_LABELS: dict[str, str] = {"high": "have", "medium": "partial", "low": "missing"}


def label_for_confidence(score: float) -> str:
    for floor, label in CONFIDENCE_BUCKETS:
        if score >= floor:
            return label
    return CONFIDENCE_BUCKETS[-1][1]


def gap_label_for_confidence(score: float) -> str:
    return GAP_ANALYSIS_LABELS[label_for_confidence(score)]


def medium_floor() -> float:
    """The 'medium' floor — resume/review.py's REVIEW_THRESHOLD and the
    skill-gap 'missing' cutoff must both equal this. Exposed as a function
    (rather than relying on callers to index CONFIDENCE_BUCKETS directly)
    so the intent is explicit at each call site."""
    return next(floor for floor, label in CONFIDENCE_BUCKETS if label == "medium")
