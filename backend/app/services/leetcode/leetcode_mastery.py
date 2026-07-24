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


def get_mastery_level(problems_solved: int) -> str:
    if problems_solved <= 0:
        return "Not Practiced"
    for ceiling, label in MASTERY_THRESHOLDS[1:]:
        if problems_solved <= ceiling:
            return label
    return MASTERY_MAX_LABEL