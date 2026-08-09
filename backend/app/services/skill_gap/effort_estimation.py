# backend/app/services/skill_gap/effort_estimation.py
"""Unchanged copy of jobs/effort_estimation.py, moved under skill_gap/
since it's genuinely comparison/planning logic (how long WILL IT TAKE
THIS user to close a gap), not a fact about the role."""

WEEKS_PER_MISSING_SKILL = 1.5


def estimate_weeks(missing_count: int) -> int:
    if missing_count == 0:
        return 0
    return max(1, round(missing_count * WEEKS_PER_MISSING_SKILL))