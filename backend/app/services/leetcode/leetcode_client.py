import json
from datetime import datetime, timedelta, timezone

import httpx

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"

# Combined, single-request query. Pulls tag-level solve counts, the
# easy/medium/hard breakdown, contest standing, and the raw submission
# calendar (used below to derive streaks). Unofficial and undocumented —
# this is exactly why every call is funneled through LeetCodeSyncError.
PROFILE_QUERY = """
query userProfile($username: String!) {
  matchedUser(username: $username) {
    username
    submitStats: submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
      }
    }
    userCalendar {
      streak
      totalActiveDays
      submissionCalendar
    }
    tagProblemCounts {
      advanced { tagName tagSlug problemsSolved }
      intermediate { tagName tagSlug problemsSolved }
      fundamental { tagName tagSlug problemsSolved }
    }
  }
  userContestRanking(username: $username) {
    attendedContestsCount
    rating
    globalRanking
  }
}
"""


class LeetCodeSyncError(Exception):
    """Raised whenever the unofficial LeetCode endpoint can't be reached or
    returns something we don't recognize. Callers should catch this
    specifically and fall back to the manual entry form rather than
    letting it surface as an unhandled crash.
    """


def _compute_streaks(submission_calendar: dict[int, int]) -> tuple[int, int]:
    """submission_calendar: {unix_day_timestamp: submission_count}.
    Returns (longest_streak, current_streak) measured in consecutive
    active days.
    """
    active_days = sorted(ts for ts, count in submission_calendar.items() if count > 0)
    if not active_days:
        return 0, 0

    longest = 1
    run = 1
    for prev, curr in zip(active_days, active_days[1:]):
        if curr - prev == 86400:
            run += 1
            longest = max(longest, run)
        elif curr - prev != 0:
            run = 1

    today_ts = int(
        datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )
    most_recent = active_days[-1]
    # If the most recent activity is older than yesterday, the streak is dead.
    if today_ts - most_recent > 86400:
        return longest, 0

    current = 1
    idx = len(active_days) - 1
    while idx > 0 and active_days[idx] - active_days[idx - 1] == 86400:
        current += 1
        idx -= 1

    return longest, current


def _active_days_last_30(submission_calendar: dict[int, int]) -> int:
    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp())
    return sum(1 for ts, count in submission_calendar.items() if count > 0 and ts >= cutoff_ts)


async def fetch_leetcode_profile(username: str, graphql_url: str = LEETCODE_GRAPHQL_URL) -> dict:
    """Returns:
    {
        "tag_counts": {tag_slug: solved_count, ...},
        "total_solved": int, "easy": int, "medium": int, "hard": int,
        "contest_rating": float | None, "global_ranking": int | None,
        "active_days_last_30": int, "longest_streak": int, "current_streak": int,
    }
    """
    if not username:
        raise LeetCodeSyncError("LEETCODE_USERNAME is not set")

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                graphql_url,
                json={"query": PROFILE_QUERY, "variables": {"username": username}},
                headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"},
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        raise LeetCodeSyncError(f"LeetCode endpoint unreachable: {e}") from e

    if "errors" in data:
        raise LeetCodeSyncError(f"LeetCode GraphQL errors: {data['errors']}")

    try:
        matched_user = data["data"]["matchedUser"]
        if matched_user is None:
            raise LeetCodeSyncError(f"No LeetCode user found for username '{username}'")

        tag_buckets = matched_user["tagProblemCounts"]
        tag_counts: dict[str, int] = {}
        for bucket_name in ("fundamental", "intermediate", "advanced"):
            for entry in tag_buckets.get(bucket_name, []):
                tag_counts[entry["tagSlug"]] = entry["problemsSolved"]

        difficulty_counts = {"All": 0, "Easy": 0, "Medium": 0, "Hard": 0}
        for entry in matched_user["submitStats"]["acSubmissionNum"]:
            difficulty_counts[entry["difficulty"]] = entry["count"]

        calendar_raw = matched_user["userCalendar"]["submissionCalendar"]
        submission_calendar = (
            {int(k): v for k, v in json.loads(calendar_raw).items()} if calendar_raw else {}
        )

        contest = data["data"].get("userContestRanking") or {}

    except (KeyError, TypeError, json.JSONDecodeError) as e:
        raise LeetCodeSyncError(f"Unexpected LeetCode response shape: {e}") from e

    longest_streak, current_streak = _compute_streaks(submission_calendar)

    return {
        "tag_counts": tag_counts,
        "total_solved": difficulty_counts["All"],
        "easy": difficulty_counts["Easy"],
        "medium": difficulty_counts["Medium"],
        "hard": difficulty_counts["Hard"],
        "contest_rating": contest.get("rating"),
        "global_ranking": contest.get("globalRanking"),
        "active_days_last_30": _active_days_last_30(submission_calendar),
        "longest_streak": longest_streak,
        "current_streak": current_streak,
    }