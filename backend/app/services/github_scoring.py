"""Rule-based repository scoring (0-100). Answers 'which projects are
actually strongest' instead of conflating strength with recent commit
volume (a project that's finished and stable will look 'weak' by
activity alone, which is exactly the wrong signal to send Resume
Reviewer or the Interview Response Agent).
"""
from datetime import datetime, timezone

MAX_SCORE = 100


def score_repository(
    *,
    commits_30d: int,
    stars: int,
    forks: int,
    has_readme: bool,
    has_ci: bool,
    has_tests: bool,
    size_kb: int,
    language_count: int,
    topic_count: int,
    pushed_at: str | None,
    archived: bool,
    has_description: bool,
) -> dict:
    # Activity (0-25) — capped so one hyperactive repo doesn't blow the scale
    activity = min(commits_30d, 25) / 25 * 25

    # Maintenance/Recency (0-20) — decays smoothly, floors near 0 past ~180 days idle
    maintenance = 0.0
    if pushed_at:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        days_since_push = (datetime.now(timezone.utc) - pushed).days
        maintenance = max(0.0, 20.0 - (days_since_push / 180 * 20))

    # Documentation (0-15)
    documentation = 0.0
    if has_readme:
        documentation += 10.0
    if has_description:
        documentation += 5.0

    # Engineering/Testing/CI & Complexity (0-40)
    engineering = 0.0
    if has_tests:
        engineering += 15.0
    if has_ci:
        engineering += 10.0
    engineering += min(language_count, 4) / 4 * 6
    engineering += min(topic_count, 5) / 5 * 4
    engineering += min(size_kb, 5000) / 5000 * 3
    engineering += min(stars + forks, 10) / 10 * 2

    if archived:
        # Frozen in time — scale all components
        activity *= 0.7
        maintenance *= 0.7
        documentation *= 0.7
        engineering *= 0.7

    overall = activity + maintenance + documentation + engineering

    return {
        "overall": round(min(overall, MAX_SCORE)),
        "breakdown": {
            "activity": round(activity),
            "documentation": round(documentation),
            "engineering": round(engineering),
            "maintenance": round(maintenance),
        },
    }