"""Rule-based, not LLM-based — same philosophy as resume/confidence.py's
confidence formula (§4.3 of the design doc): start simple and explainable,
only reach for an LLM-computed version later once you have real data to
validate against. One missing skill ~= 1.5 weeks of focused study; never
recommend less than 1 week if anything is missing at all.
"""

WEEKS_PER_MISSING_SKILL = 1.5


def estimate_weeks(missing_count: int) -> int:
    if missing_count == 0:
        return 0
    return max(1, round(missing_count * WEEKS_PER_MISSING_SKILL))