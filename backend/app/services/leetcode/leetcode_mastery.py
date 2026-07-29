# backend/app/services/leetcode/leetcode_mastery.py
"""Deterministic mastery thresholds. Centralized here so every consumer
(dsa_profile, interview_readiness, topic_mastery) uses one vocabulary
instead of each re-inventing its own cutoffs.

Tune these over time as you gather more real snapshot history — per
the design doc's own guidance in §4.3 for confidence scoring.
"""

MASTERY_THRESHOLDS: list[tuple[int, str]] = [
    (0, "Not Practiced"),
    (3, "Introduced"),
    (10, "Some Practice"),
    (25, "Consistent Practice"),
]
MASTERY_MAX_LABEL = "Extensive Practice"
MASTERY_ORDER = ["Not Practiced", "Introduced", "Some Practice", "Consistent Practice", "Extensive Practice"]

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


def get_mastery_level(problems_solved: int) -> str:
    if problems_solved <= 0:
        return "Not Practiced"
    for ceiling, label in MASTERY_THRESHOLDS[1:]:
        if problems_solved <= ceiling:
            return label
    return MASTERY_MAX_LABEL


def _decay_levels_for(days_since_progress: int) -> int:
    for ceiling, levels in DECAY_STEPS:
        if days_since_progress <= ceiling:
            return levels
    return MAX_DECAY_LEVELS


def get_effective_mastery(problems_solved: int, days_since_progress: int | None) -> tuple[str, bool]:
    """Returns (effective_mastery_label, is_stale).

    `days_since_progress` is the number of days since this topic's
    solved-count last increased, derived from real leetcode_snapshots
    history (see leetcode_recency.py) — never a guess. If it's None
    (no history to derive it from yet, e.g. a topic solved for the
    first time on the very first sync), no decay is applied since we
    can't fairly penalize what we can't measure.
    """
    base = get_mastery_level(problems_solved)
    if problems_solved <= 0 or days_since_progress is None:
        return base, False

    downgrade = _decay_levels_for(days_since_progress)
    if downgrade == 0:
        return base, False

    base_idx = MASTERY_ORDER.index(base)
    floor_idx = MASTERY_ORDER.index(FLOOR_LEVEL_IF_EVER_PRACTICED)
    new_idx = max(floor_idx, base_idx - downgrade)
    return MASTERY_ORDER[new_idx], True