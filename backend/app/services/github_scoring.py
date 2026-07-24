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
) -> int:
    score = 0.0

    # Activity (0-25) — capped so one hyperactive repo doesn't blow the scale
    score += min(commits_30d, 25) / 25 * 25

    # Recency (0-20) — decays smoothly, floors near 0 past ~180 days idle
    if pushed_at:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        days_since_push = (datetime.now(timezone.utc) - pushed).days
        score += max(0, 20 - (days_since_push / 180 * 20))

    # Documentation (0-15)
    if has_readme:
        score += 10
    if has_description:
        score += 5

    # Testing (0-15)
    if has_tests:
        score += 15

    # CI/CD (0-10)
    if has_ci:
        score += 10

    # Complexity / maturity (0-15)
    score += min(language_count, 4) / 4 * 6
    score += min(topic_count, 5) / 5 * 4
    score += min(size_kb, 5000) / 5000 * 3
    score += min(stars + forks, 10) / 10 * 2

    if archived:
        # Frozen in time — still real evidence, shouldn't outrank active work
        score *= 0.7

    return round(min(score, MAX_SCORE))