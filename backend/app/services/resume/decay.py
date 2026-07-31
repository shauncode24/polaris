"""Recency decay for skill evidence weight — same explainable-formula
philosophy as leetcode_mastery.py's DECAY_STEPS, applied to the general
SkillEvidence confidence formula. Before this existed, skill confidence
only ever grew: a resume bullet from three years ago with zero
corroborating activity since read as fully confident, forever. Evidence
age now discounts its own weight, so confidence reflects how CURRENT
the evidence is, not just whether it was ever true once.
"""
from datetime import datetime, timezone

# (days_old_ceiling, weight_multiplier)
DECAY_STEPS: list[tuple[int, float]] = [
    (90, 1.0),   # fresh — full weight
    (180, 0.85),
    (365, 0.65),
]
FLOOR_MULTIPLIER = 0.45  # evidence never fully disappears — it was real once


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