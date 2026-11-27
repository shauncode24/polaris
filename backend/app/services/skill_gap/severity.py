"""How much a gap matters for a job.

Deterministic, from two facts: how the job asks for the skill, and whether
the user has weak evidence for it (partial) or not enough to count at all
(missing).

                 missing     partial
    required     critical    moderate
    implicit     moderate    minor
    nice to have minor       minor
"""
from app.schemas.skill_gap.skill_gap import Severity

_SEVERITY: dict[str, dict[str, Severity]] = {
    "required": {"missing": "critical", "partial": "moderate"},
    "implicit": {"missing": "moderate", "partial": "minor"},
    "nice_to_have": {"missing": "minor", "partial": "minor"},
}


def gap_severity(requirement_type: str, status: str) -> Severity:
    """`status` is "missing" or "partial". An unrecognised requirement type
    is treated as the least demanding one.
    """
    return _SEVERITY.get(requirement_type, _SEVERITY["nice_to_have"])[status]
