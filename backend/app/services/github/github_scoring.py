"""Rich, user-facing per-repo score (0-100) with a full breakdown.
Answers 'which projects are actually strongest' instead of conflating
strength with recent commit volume, and folds in three signals that used
to be invisible: fork contribution, commit-message hygiene, and PR/review
collaboration. Still a fully explainable formula — no LLM anywhere in
this file.

Note on coexistence with github_analyzer.py:
  github_analyzer.analyze_repo() computes a SIMPLER internal score
  (quality_score 0-100, activity_score 0-100 separately) that is stored
  in GithubProjectAnalysis and used for tier assignment and portfolio
  sorting. That score intentionally omits hygiene/collaboration/maintenance
  to stay cheap and stable for DB queries. THIS score is the canonical
  user-facing number; the analyzer's split is an internal signal.
  combined_repo_score() in github_analyzer.py is the shared blending
  function for the internal path.
"""
from datetime import datetime, timezone

MAX_SCORE = 100
FORK_CONTRIBUTION_THRESHOLD = 5   # commits authored by the user, all-time
FORK_PENALTY_MULTIPLIER = 0.4     # applied when a fork has no real added work


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
    is_fork: bool = False,
    fork_contribution_commits: int = 0,
    commit_hygiene_score: float = 0.0,
    collaboration_score: float = 0.0,
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

    # Engineering/Testing/CI & Complexity (0-30 — trimmed from 40 to make
    # room for the two new components below without changing the max total)
    engineering = 0.0
    if has_tests:
        engineering += 12.0
    if has_ci:
        engineering += 8.0
    engineering += min(language_count, 4) / 4 * 4
    engineering += min(topic_count, 5) / 5 * 3
    engineering += min(size_kb, 5000) / 5000 * 2
    engineering += min(stars + forks, 10) / 10 * 1

    # Commit hygiene (0-5) — message quality & steady-vs-burst pacing
    hygiene = (commit_hygiene_score / 100) * 5

    # Collaboration (0-5) — real PR/review activity vs. solo commits only
    collaboration = (collaboration_score / 100) * 5

    if archived:
        # Frozen in time — scale all components
        activity *= 0.7
        maintenance *= 0.7
        documentation *= 0.7
        engineering *= 0.7
        hygiene *= 0.7
        collaboration *= 0.7

    overall = activity + maintenance + documentation + engineering + hygiene + collaboration

    # Fork penalty: a fork with little to no original contribution
    # shouldn't score like original work, no matter how healthy the
    # upstream repo's activity/docs/tests happen to be.
    is_meaningful_fork_contribution = fork_contribution_commits >= FORK_CONTRIBUTION_THRESHOLD
    if is_fork and not is_meaningful_fork_contribution:
        overall *= FORK_PENALTY_MULTIPLIER

    return {
        "overall": round(min(overall, MAX_SCORE)),
        "breakdown": {
            "activity": round(activity),
            "documentation": round(documentation),
            "engineering": round(engineering),
            "maintenance": round(maintenance),
            "commit_hygiene": round(hygiene),
            "collaboration": round(collaboration),
        },
        "is_fork": is_fork,
        "is_meaningful_fork_contribution": is_meaningful_fork_contribution,
    }