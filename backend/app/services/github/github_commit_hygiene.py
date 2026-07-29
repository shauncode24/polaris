"""Commit-hygiene scoring — deterministic, zero LLM calls. Uses commit
messages and timestamps the sync already has API access to but never
looked at. Two independent signals: message quality (conventional-style,
non-generic, non-trivial length) and pacing (steady work vs. a last-
minute dump), same explainable-formula philosophy as github_scoring.py.
"""
import re
from collections import Counter
from datetime import datetime

CONVENTIONAL_PATTERN = re.compile(
    r"^(feat|fix|chore|docs|refactor|test|style|perf|build|ci|revert)(\([\w\-\/]+\))?:\s.+",
    re.IGNORECASE,
)
GENERIC_MESSAGES = {
    "update", "updates", "fix", "fixes", "wip", "changes", "misc", "stuff",
    "final", "final commit", "test", "asdf", "commit", "minor changes",
    "small fix", "update readme", "initial commit", "changes made", "more changes",
}
MIN_GOOD_LENGTH = 15
BURST_DAY_SHARE_THRESHOLD = 0.6
MIN_SAMPLE_FOR_BURST_CHECK = 5


def _detect_burst(timestamps: list[datetime]) -> bool:
    """True if a single calendar day accounts for >=60% of the sampled
    commits — a signal of a last-minute dump rather than steady work.
    Requires a minimum sample size so a repo with 3 total commits doesn't
    get flagged just because they happened close together.
    """
    if len(timestamps) < MIN_SAMPLE_FOR_BURST_CHECK:
        return False
    day_buckets = Counter(ts.date() for ts in timestamps)
    busiest_day_count = max(day_buckets.values())
    return (busiest_day_count / len(timestamps)) >= BURST_DAY_SHARE_THRESHOLD


def score_commit_hygiene(messages: list[str], timestamps: list[datetime]) -> dict:
    """Returns a 0-100 score plus the raw signals it was built from, so
    the UI/LLM can explain *why* a repo scored the way it did instead of
    presenting a bare number.
    """
    if not messages:
        return {
            "score": 0, "conventional_pct": 0, "generic_pct": 0,
            "avg_length": 0.0, "burst_detected": False, "sample_size": 0,
        }

    conventional = sum(1 for m in messages if CONVENTIONAL_PATTERN.match(m.strip()))
    generic = sum(1 for m in messages if m.strip().lower().rstrip(".!") in GENERIC_MESSAGES)
    avg_length = sum(len(m.strip()) for m in messages) / len(messages)

    conventional_pct = round((conventional / len(messages)) * 100)
    generic_pct = round((generic / len(messages)) * 100)
    burst_detected = _detect_burst(timestamps)

    score = 0.0
    score += conventional_pct * 0.40
    score += max(0, 100 - generic_pct * 2) * 0.35
    score += min(avg_length / MIN_GOOD_LENGTH, 1.0) * 100 * 0.15
    score += (0 if burst_detected else 100) * 0.10

    return {
        "score": round(min(score, 100)),
        "conventional_pct": conventional_pct,
        "generic_pct": generic_pct,
        "avg_length": round(avg_length, 1),
        "burst_detected": burst_detected,
        "sample_size": len(messages),
    }