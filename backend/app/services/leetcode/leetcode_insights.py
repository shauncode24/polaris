# backend/app/services/leetcode/leetcode_insights.py
"""Turns raw LeetCode sync data into interview-facing insight — 'what
does this mean for my interview prep', not 'how many Arrays problems
have I solved'. Every output field here is meant to be directly
consumable by Career Planner, Skill Gap Analyzer, or Interview
Response Agent later — if a field is just LeetCode metadata reshaped,
it belongs in the raw snapshot, not here (same rule as github_insights.py).
"""
from datetime import datetime

from app.services.leetcode.leetcode_taxonomy import topic_totals, weighted_topic_totals
from app.services.leetcode.leetcode_mastery import get_mastery_level, get_effective_mastery
from app.services.leetcode.leetcode_diversity import compute_practice_diversity


FUNDAMENTAL_TOPICS = {
    "Arrays & Hashing", "Strings", "Sliding Window", "Stack", "Queue",
    "Linked List", "Trees", "Graphs", "Binary Search", "Sorting", "Recursion", "Math"
}
ADVANCED_TOPICS = {
    "Heap", "Trie", "Dynamic Programming", "Greedy", "Backtracking",
    "Bit Manipulation", "Intervals", "Design"
}

MIN_NEW_PROBLEMS_FOR_ADHERENCE = 1

CONTEST_TREND_FLAT_THRESHOLD = 15
CONTEST_TREND_MIN_POINTS = 2

# Honest disclosure of what solved-count-derived insight can and can't
# claim, per LeetCode Module Review §3F — a trust move, not a feature.
# The unofficial LeetCode API exposes counts and a per-tag difficulty
# TIER, not per-problem process (no attempt count, no time-to-solve, no
# editorial usage), so mastery labels here are a proxy for practice
# volume/recency/difficulty-tier — never a guarantee of live interview
# performance.
DATA_CEILING_NOTE = (
    "This reads solved-problem counts, recency, and LeetCode's own fundamental/intermediate/"
    "advanced tag-difficulty tiers — the unofficial API doesn't expose attempt count, time-to-solve, "
    "or whether the editorial was used. Treat mastery labels as a proxy for practice depth, not a "
    "guarantee of interview performance."
)


def build_topic_mastery(
    tag_counts: dict[str, int],
    topic_days_since: dict[str, int | None] | None = None,
    tag_difficulty_tier: dict[str, str] | None = None,
) -> list[dict]:
    """`problems` in the returned dicts is always the real, unweighted
    solved-problem count for that topic — never replaced or hidden.
    `weighted_score` is the difficulty-weighted figure that mastery
    LABELS are actually computed from (see leetcode_taxonomy.TIER_WEIGHTS);
    it's exposed alongside `problems`, not instead of it, so nothing here
    silently inflates or hides the real number.
    """
    raw_totals = topic_totals(tag_counts)
    weighted_totals = weighted_topic_totals(tag_counts, tag_difficulty_tier)
    topic_days_since = topic_days_since or {}

    results = []
    for topic, count in raw_totals.items():
        weighted_score = weighted_totals.get(topic, 0.0)
        days_since_progress = topic_days_since.get(topic)
        effective_mastery, is_stale = get_effective_mastery(weighted_score, days_since_progress)
        results.append({
            "topic": topic,
            "problems": count,
            "weighted_score": weighted_score,
            "mastery": effective_mastery,
            "raw_mastery": get_mastery_level(weighted_score),
            "is_stale": is_stale,
            "days_since_progress": days_since_progress,
        })

    return sorted(results, key=lambda t: t["problems"], reverse=True)


def detect_blind_spots(topic_mastery: list[dict]) -> dict[str, list[str]]:
    missing_fundamentals = []
    advanced_topics = []

    for t in topic_mastery:
        if t["problems"] == 0:
            if t["topic"] in FUNDAMENTAL_TOPICS:
                missing_fundamentals.append(t["topic"])
            elif t["topic"] in ADVANCED_TOPICS:
                advanced_topics.append(t["topic"])

    return {
        "missing_fundamentals": sorted(missing_fundamentals),
        "advanced_topics": sorted(advanced_topics),
    }


def build_practice_habits(
    active_days_last_30: int,
    submissions_last_30: int,
    easy: int,
    medium: int,
    hard: int,
    longest_gap_days: int,
) -> dict:
    if active_days_last_30 <= 3:
        consistency = "Low"
    elif active_days_last_30 <= 10:
        consistency = "Moderate"
    elif active_days_last_30 <= 20:
        consistency = "Good"
    else:
        consistency = "High"

    avg_session_length = (
        round(submissions_last_30 / active_days_last_30, 1) if active_days_last_30 > 0 else 0.0
    )

    difficulty_counts = {"Easy": easy, "Medium": medium, "Hard": hard}
    preferred_difficulty = max(difficulty_counts, key=difficulty_counts.get) if any(difficulty_counts.values()) else "None"

    return {
        "consistency": consistency,
        "sessions_last_30_days": active_days_last_30,
        "preferred_difficulty": preferred_difficulty,
        "average_session_length": avg_session_length,
        "longest_gap_days": longest_gap_days,
    }


def build_difficulty_insight(easy: int, medium: int, hard: int) -> str:
    """Kept as a fact string fed to the AI Coach narrative (leetcode_review.py's
    prompt) — per LeetCode Module Review §3, this is deliberately NOT
    surfaced as a standalone UI insight (it was templated sentences with
    no real inference); it's now only prompt context."""
    total = easy + medium + hard
    if total == 0:
        return "No problems solved yet — start with Easy problems to build fundamentals."

    easy_pct = easy / total
    medium_pct = medium / total

    sentences = [f"{round(easy_pct * 100)}% of your solved problems are Easy."]

    if medium_pct >= 0.4:
        sentences.append("Your Medium coverage is strong.")
    elif medium > 0:
        sentences.append("Your Medium coverage is growing.")
    else:
        sentences.append("Medium problems remain unexplored.")

    if hard > 0:
        sentences.append("You have explored some Hard problems.")
    else:
        sentences.append("Hard problems remain largely unexplored.")

    return " ".join(sentences)


def build_progress(
    current_topic_totals: dict[str, int],
    previous_topic_totals: dict[str, int] | None,
    current_total_solved: int,
    previous_total_solved: int | None,
    easy: int,
    previous_easy: int | None,
    medium: int,
    previous_medium: int | None,
    hard: int,
    previous_hard: int | None,
    topic_mastery: list[dict],
) -> dict:
    previous_topic_totals = previous_topic_totals or {}
    new_problems = (
        current_total_solved - previous_total_solved if previous_total_solved is not None else current_total_solved
    )
    new_topics = [
        topic for topic, count in current_topic_totals.items()
        if count > 0 and previous_topic_totals.get(topic, 0) == 0
    ]

    difficulty_change = {
        "easy": max(0, easy - previous_easy) if previous_easy is not None else easy,
        "medium": max(0, medium - previous_medium) if previous_medium is not None else medium,
        "hard": max(0, hard - previous_hard) if previous_hard is not None else hard,
    }

    mastery_changes = []
    for item in topic_mastery:
        topic = item["topic"]
        curr_level = item["mastery"]

        # NOTE: prev_level is derived from the raw (unweighted) previous
        # count for simplicity — historical per-tag difficulty tiers
        # aren't persisted per snapshot. Since weighted score is always
        # >= raw count (weights are >= 1.0), this can only make a real
        # level-up land here at least as early as an unweighted
        # comparison would, never falsely later — safe to leave as a
        # best-effort trend, not an authoritative mastery diff.
        prev_count = previous_topic_totals.get(topic, 0)
        prev_level = get_mastery_level(prev_count)

        if prev_level != curr_level:
            mastery_changes.append({
                "topic": topic,
                "from": prev_level,
                "to": curr_level,
            })

    return {
        "new_problems": new_problems,
        "new_topics": new_topics,
        "mastery_changes": mastery_changes,
        "difficulty_change": difficulty_change,
    }


def build_recommendations(topic_mastery: list[dict], easy: int, medium: int, hard: int) -> list[dict]:
    recommendations = []

    unpracticed_fundamentals = [
        t["topic"] for t in topic_mastery
        if t["topic"] in FUNDAMENTAL_TOPICS and t["mastery"] == "Not Practiced"
    ]
    for topic in unpracticed_fundamentals[:2]:
        recommendations.append({
            "priority": "High",
            "reason": f"No {topic} problems solved.",
            "action": f"Solve 10 {topic} problems.",
        })

    stale_topics_info = [t for t in topic_mastery if t.get("is_stale") and t["problems"] > 0]
    for info in stale_topics_info[:2]:
        recommendations.append({
            "priority": "High",
            "reason": f"{info['topic']} hasn't seen new solves in {info['days_since_progress']} days — mastery is decaying.",
            "action": f"Revisit {info['topic']} with 3-5 fresh problems to keep it interview-ready.",
        })

    total = easy + medium + hard
    if total > 0 and (easy / total) >= 0.7:
        recommendations.append({
            "priority": "Medium",
            "reason": "Practice is heavily Easy-focused.",
            "action": "Aim for 15 Medium problems this month.",
        })

    extensively_practiced = [
        t["topic"] for t in topic_mastery
        if t["mastery"] in ("Consistent Practice", "Extensive Practice")
    ]
    if extensively_practiced:
        topic_repr = extensively_practiced[0]
        missing_some = [t["topic"] for t in topic_mastery if t["mastery"] in ("Not Practiced", "Introduced")]
        next_focus = "DP and Trees"
        if missing_some:
            next_focus = " and ".join(missing_some[:2])
        recommendations.append({
            "priority": "Low",
            "reason": f"{topic_repr} are already well represented.",
            "action": f"Shift focus toward {next_focus}.",
        })

    return recommendations


def build_contest_trajectory(rating_history: list[dict]) -> dict:
    rated_points = [p for p in rating_history if p.get("rating") is not None]

    if len(rated_points) < CONTEST_TREND_MIN_POINTS:
        return {
            "trend": "insufficient_data" if rated_points else "no_contests",
            "points": rated_points,
            "change_since_first": None,
            "weeks_tracked": 0,
        }

    first, last = rated_points[0], rated_points[-1]
    change = round(last["rating"] - first["rating"], 1)

    if abs(change) <= CONTEST_TREND_FLAT_THRESHOLD:
        trend = "flat"
    elif change > 0:
        trend = "improving"
    else:
        trend = "declining"

    try:
        first_dt = datetime.fromisoformat(first["taken_at"])
        last_dt = datetime.fromisoformat(last["taken_at"])
        weeks_tracked = max(1, round((last_dt - first_dt).days / 7))
    except (ValueError, TypeError):
        weeks_tracked = None

    return {
        "trend": trend,
        "points": rated_points,
        "change_since_first": change,
        "weeks_tracked": weeks_tracked,
    }


def build_plan_adherence(
    recommended_topics: list[str],
    recommended_at: str | None,
    current_topic_totals: dict[str, int],
    previous_topic_totals: dict[str, int] | None,
) -> list[dict]:
    if not recommended_topics or recommended_at is None:
        return []

    previous_topic_totals = previous_topic_totals or {}
    adherence = []
    for topic in recommended_topics:
        current = current_topic_totals.get(topic, 0)
        previous = previous_topic_totals.get(topic, 0)
        new_problems = max(0, current - previous)
        adherence.append({
            "topic": topic,
            "recommended_at": recommended_at,
            "new_problems_since_recommendation": new_problems,
            "status": "followed" if new_problems >= MIN_NEW_PROBLEMS_FOR_ADHERENCE else "not_yet_followed",
        })
    return adherence


def build_leetcode_insights(
    *,
    tag_counts: dict[str, int],
    previous_tag_counts: dict[str, int] | None,
    total_solved: int,
    previous_total_solved: int | None,
    easy: int,
    previous_easy: int | None,
    medium: int,
    previous_medium: int | None,
    hard: int,
    previous_hard: int | None,
    attended_contests_count: int,
    active_days_last_30: int,
    submissions_last_30: int,
    longest_gap_days: int,
    reinforced_skills: list[str],
    new_skills: list[str],
    unchanged_skills: list[str],
    topic_days_since: dict[str, int | None] | None = None,
    contest_rating_history: list[dict] | None = None,
    plan_adherence: list[dict] | None = None,
    tag_difficulty_tier: dict[str, str] | None = None,
) -> dict:
    topic_mastery = build_topic_mastery(tag_counts, topic_days_since, tag_difficulty_tier)
    blind_spots = detect_blind_spots(topic_mastery)
    practice_habits = build_practice_habits(
        active_days_last_30, submissions_last_30, easy, medium, hard, longest_gap_days
    )
    difficulty_insight = build_difficulty_insight(easy, medium, hard)

    previous_topic_totals = (
        topic_totals(previous_tag_counts) if previous_tag_counts is not None else None
    )
    current_topic_totals = {t["topic"]: t["problems"] for t in topic_mastery}
    progress = build_progress(
        current_topic_totals, previous_topic_totals,
        total_solved, previous_total_solved,
        easy, previous_easy,
        medium, previous_medium,
        hard, previous_hard,
        topic_mastery,
    )
    recommendations = build_recommendations(topic_mastery, easy, medium, hard)
    contest_trajectory = build_contest_trajectory(contest_rating_history or [])

    practice_diversity = compute_practice_diversity(current_topic_totals, previous_topic_totals)

    return {
        "topic_mastery": topic_mastery,
        "blind_spots": blind_spots,
        "practice_habits": practice_habits,
        "difficulty_insight": difficulty_insight,
        "progress": progress,
        "recommendations": recommendations,
        "contest_trajectory": contest_trajectory,
        "plan_adherence": plan_adherence or [],
        "practice_diversity": practice_diversity,
        "data_ceiling_note": DATA_CEILING_NOTE,
        "skill_evidence_detail": {
            "reinforced": reinforced_skills,
            "new": new_skills,
            "unchanged": unchanged_skills,
        },
    }