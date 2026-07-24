# backend/app/services/leetcode/leetcode_insights.py
"""Turns raw LeetCode sync data into interview-facing insight — 'what
does this mean for my interview prep', not 'how many Arrays problems
have I solved'. Every output field here is meant to be directly
consumable by Career Planner, Skill Gap Analyzer, or Interview
Response Agent later — if a field is just LeetCode metadata reshaped,
it belongs in the raw snapshot, not here (same rule as github_insights.py).
"""
from app.services.leetcode.leetcode_taxonomy import topic_totals
from app.services.leetcode.leetcode_mastery import get_mastery_level


FUNDAMENTAL_TOPICS = {
    "Arrays & Hashing", "Strings", "Sliding Window", "Stack", "Queue",
    "Linked List", "Trees", "Graphs", "Binary Search", "Sorting", "Recursion", "Math"
}
ADVANCED_TOPICS = {
    "Heap", "Trie", "Dynamic Programming", "Greedy", "Backtracking",
    "Bit Manipulation", "Intervals", "Design"
}


def build_topic_mastery(tag_counts: dict[str, int]) -> list[dict]:
    totals = topic_totals(tag_counts)
    return [
        {"topic": topic, "problems": count, "mastery": get_mastery_level(count)}
        for topic, count in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    ]


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
    total = easy + medium + hard
    if total == 0:
        return "No problems solved yet — start with Easy problems to build fundamentals."

    easy_pct = easy / total
    medium_pct = medium / total

    sentences = []
    sentences.append(f"{round(easy_pct * 100)}% of your solved problems are Easy.")

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

    # 1. High Priority for blind spots in fundamentals
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

    # 2. Medium Priority for Easy-heavy split
    total = easy + medium + hard
    if total > 0 and (easy / total) >= 0.7:
        recommendations.append({
            "priority": "Medium",
            "reason": "Practice is heavily Easy-focused.",
            "action": "Aim for 15 Medium problems this month.",
        })

    # 3. Low Priority for highly represented areas
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
) -> dict:
    topic_mastery = build_topic_mastery(tag_counts)
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

    return {
        "topic_mastery": topic_mastery,
        "blind_spots": blind_spots,
        "practice_habits": practice_habits,
        "difficulty_insight": difficulty_insight,
        "progress": progress,
        "recommendations": recommendations,
        "skill_evidence_detail": {
            "reinforced": reinforced_skills,
            "new": new_skills,
            "unchanged": unchanged_skills,
        },
    }