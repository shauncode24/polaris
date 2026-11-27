import pytest

from app.services.skill_gap.severity import gap_severity


@pytest.mark.parametrize(
    "requirement_type, status, severity",
    [
        ("required", "missing", "critical"),
        ("required", "partial", "moderate"),
        ("implicit", "missing", "moderate"),
        ("implicit", "partial", "minor"),
        ("nice_to_have", "missing", "minor"),
        ("nice_to_have", "partial", "minor"),
        ("something_else", "missing", "minor"),
    ],
)
def test_severity_follows_how_the_job_asks_and_how_far_short_the_evidence_falls(
    requirement_type, status, severity
):
    assert gap_severity(requirement_type, status) == severity
