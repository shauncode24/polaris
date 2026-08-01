# backend/app/services/leetcode/leetcode_mastery.py
"""Deterministic mastery thresholds. Centralized here so every consumer
(dsa_profile, interview_readiness, topic_mastery) uses one vocabulary
instead of each re-inventing its own cutoffs.

As of the difficulty-weighting change, these thresholds are evaluated
against a difficulty-weighted score (leetcode_taxonomy.weighted_topic_totals),
not the raw solved-problem count — a topic with heavier advanced-tier
solving reaches a mastery label sooner than the same raw count made up
entirely of fundamental-tier solves. The functions below don't care
whether the number they receive is weighted or raw; that decision is
made once, by the caller (leetcode_insights.build_topic_mastery).

Tune these over time as you gather more real snapshot history — per
the design doc's own guidance in §4.3 for confidence scoring.
"""

MASTERY_THRESHOLDS: list[tuple[float, str]] = [
    (0, "Not Practiced"),
    (3, "Introduced"),
    (10, "Some Practice"),
    (25, "Consistent Practice"),
]
MASTERY_MAX_LABEL = "Extensive Practice"
MASTERY_ORDER = ["Not Practiced", "Introduced", "Some Practice", "Consistent Practice", "Extensive Practice"]
# Canonical 0-1 mastery-to-score base. Every cross-module consumer that
# needs to turn a mastery LABEL into a number should derive from THIS,
# not define its own literal dict — that's what let engineering_quadrant.py
# and company_readiness.py drift into two independently-hand-tuned tables
# with no visible link between them (audit finding, module review).
MASTERY_SCORE_BASE: dict[str, float] = {
    "Not Practiced": 0.0,
    "Introduced": 0.25,
    "Some Practice": 0.5,
    "Consistent Practice": 0.8,
    "Extensive Practice": 1.0,
}

# company_readiness.py's ONLY sanctioned divergence from MASTERY_SCORE_BASE:
# light/moderate practice gets a small credit bump at company-matching
# resolution (a recommendation-facing question — "am I close?") without
# touching the base scale used for quadrant CLASSIFICATION (a coarser,
# stricter question). If this bump ever needs to change, it changes here,
# once, instead of inside a second hardcoded dict.
COMPANY_READINESS_SCORE_BUMP: dict[str, float] = {
    "Not Practiced": 0.0,
    "Introduced": 0.05,
    "Some Practice": 0.10,
    "Consistent Practice": 0.05,
    "Extensive Practice": 0.0,
}
# Recency decay — a topic with real solved-problem history that hasn't
# been touched in months shouldn't read identically to one practiced
# last week. Interview readiness decays; the mastery label should too.
# (days_since_last_progress_ceiling, levels_to_downgrade)
DECAY_STEPS: list[tuple[int, int]] = [
    (60, 0),   # practiced within ~2 months: no decay
    (120, 1),  # 2-4 months stale: downgrade one level
]
MAX_DECAY_LEVELS = 2  # beyond ~4 months: downgrade two levels
FLOOR_LEVEL_IF_EVER_PRACTICED = "Introduced"  # never decay below this if problems_solved > 0


def get_mastery_level(weighted_score: float) -> str:
    """`weighted_score`: a difficulty-weighted topic score (see
    leetcode_taxonomy.weighted_topic_totals). Accepts a plain raw count
    too — the thresholds work identically either way, they just mean
    slightly different things depending on what the caller passed in.
    """
    if weighted_score <= 0:
        return "Not Practiced"
    for ceiling, label in MASTERY_THRESHOLDS[1:]:
        if weighted_score <= ceiling:
            return label
    return MASTERY_MAX_LABEL


def _decay_levels_for(days_since_progress: int) -> int:
    for ceiling, levels in DECAY_STEPS:
        if days_since_progress <= ceiling:
            return levels
    return MAX_DECAY_LEVELS


def get_effective_mastery(weighted_score: float, days_since_progress: int | None) -> tuple[str, bool]:
    """Returns (effective_mastery_label, is_stale).
    ...
    KNOWN LIMITATION: a topic solved exactly once, on a single historical
    sync, with no subsequent sync ever recording a second data point for
    it, has no baseline to measure a gap FROM — days_since_progress stays
    None forever for that topic, so it can never be flagged stale, even
    a year later. This is a real coverage gap for infrequently-syncing
    users, not a bug: there is no honest way to compute staleness without
    a second recorded observation.
    """
    base = get_mastery_level(weighted_score)
    if weighted_score <= 0 or days_since_progress is None:
        return base, False

    downgrade = _decay_levels_for(days_since_progress)
    if downgrade == 0:
        return base, False

    base_idx = MASTERY_ORDER.index(base)
    floor_idx = MASTERY_ORDER.index(FLOOR_LEVEL_IF_EVER_PRACTICED)
    new_idx = max(floor_idx, base_idx - downgrade)
    return MASTERY_ORDER[new_idx], True