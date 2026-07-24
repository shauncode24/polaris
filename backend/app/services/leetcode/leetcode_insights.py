# backend/app/services/leetcode/leetcode_insights.py
"""Turns raw LeetCode sync data into interview-facing insight — 'what
does this mean for my interview prep', not 'how many Arrays problems
have I solved'. Every output field here is meant to be directly
consumable by Career Planner, Skill Gap Analyzer, or Interview
Response Agent later — if a field is just LeetCode metadata reshaped,
it belongs in the raw snapshot, not here (same rule as github_insights.py).
"""
from app.services.leetcode.leetcode_taxonomy import CANONICAL_TOPICS, topic_totals
from app.services.leetcode.leetcode_mastery import get_mastery_level


def build_topic_mastery(tag_counts: dict[str, int]) -> list[dict]:
    totals = topic_totals(tag_counts)
    return [
        {"topic": topic, "problems": count, "mastery": get_mastery_level(count)}
        for topic, count in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    ]


def build_dsa_profile(topic_mastery: list[dict]) -> dict:
    strong = [t for t in topic_mastery if t["mastery"] in ("Strong", "Advanced")]
    developing = [t for t in topic_mastery if t["mastery"] in ("Developing", "Introduced")]
    weak = [t for t in topic_mastery if t["mastery"] == "Not Started"]
    return {
        "strong_areas": [{"category": t["topic"], "problems": t["problems"]} for t in strong],
        "developing_areas": [{"category": t["topic"], "problems": t["problems"]} for t in developing],
        "weak_areas": [{"category": t["topic"], "problems": t["problems"]} for t in weak],
    }


def detect_blind_spots(topic_mastery: list[dict]) -> list[str]:
    return [t["topic"] for t in topic_mastery if t["problems"] == 0]


def build_interview_readiness(topic_mastery: list[dict]) -> dict[str, str]:
    # Same vocabulary as topic_mastery on purpose (see mastery module docstring) —
    # a Career Planner reading either field gets a consistent answer.
    return {t["topic"].lower().replace(" & ", "_").replace(" ", "_"): t["mastery"] for t in topic_mastery}


def build_practice_habits(
    active_days_last_30: int,
    submissions_last_30: int,
    easy: int,
    medium: int,
    hard: int,
    attended_contests_count: int,
) -> dict:
    if active_days_last_30 <= 3:
        consistency = "Low"
    elif active_days_last_30 <= 10:
        consistency = "Moderate"
    elif active_days_last_30 <= 20:
        consistency = "Good"
    else:
        consistency = "High"

    avg_per_session = (
        round(submissions_last_30 / active_days_last_30, 1) if active_days_last_30 > 0 else 0.0
    )

    difficulty_counts = {"Easy": easy, "Medium": medium, "Hard": hard}
    preferred_difficulty = max(difficulty_counts, key=difficulty_counts.get) if any(difficulty_counts.values()) else "None"

    if attended_contests_count == 0:
        contest_participation = "None"
    elif attended_contests_count <= 3:
        contest_participation = "Occasional"
    else:
        contest_participation = "Active"

    return {
        "consistency": consistency,
        "average_problems_per_session": avg_per_session,
        "preferred_difficulty": preferred_difficulty,
        "contest_participation": contest_participation,
    }


def build_difficulty_insight(easy: int, medium: int, hard: int) -> str:
    total = easy + medium + hard
    if total == 0:
        return "No problems solved yet — start with Easy problems to build fundamentals."

    easy_pct = easy / total
    medium_pct = medium / total

    if easy_pct >= 0.7:
        msg = "Most of your practice is concentrated on Easy problems."
        if medium < easy * 0.3:
            msg += " Medium coverage is still limited — consider increasing Medium problem practice before starting Hard questions."
        return msg
    if medium_pct >= 0.4 and hard > 0:
        return "Your practice is well distributed across difficulties, with solid Medium and some Hard coverage — a good sign for interview readiness."
    if medium_pct >= 0.4:
        return "Good Medium-level coverage. Adding some Hard problems would round out interview readiness."
    return "Practice is fairly evenly split across difficulties."


def build_progress(
    current_topic_totals: dict[str, int],
    previous_topic_totals: dict[str, int] | None,
    current_total_solved: int,
    previous_total_solved: int | None,
    current_rating: float | None,
    previous_rating: float | None,
    new_skill_evidence: list[str],
) -> dict:
    previous_topic_totals = previous_topic_totals or {}
    problems_solved_delta = (
        current_total_solved - previous_total_solved if previous_total_solved is not None else current_total_solved
    )
    new_topics = [
        topic for topic, count in current_topic_totals.items()
        if count > 0 and previous_topic_totals.get(topic, 0) == 0
    ]
    rating_change = (
        round(current_rating - previous_rating, 1)
        if current_rating is not None and previous_rating is not None
        else None
    )

    return {
        "problems_solved": problems_solved_delta,
        "new_topics": new_topics,
        "contest_rating_change": rating_change,
        "new_skill_evidence": new_skill_evidence,
    }


def build_leetcode_insights(
    *,
    tag_counts: dict[str, int],
    previous_tag_counts: dict[str, int] | None,
    total_solved: int,
    previous_total_solved: int | None,
    easy: int,
    medium: int,
    hard: int,
    contest_rating: float | None,
    previous_contest_rating: float | None,
    attended_contests_count: int,
    active_days_last_30: int,
    submissions_last_30: int,
    reinforced_skills: list[str],
    new_skills: list[str],
    unchanged_skills: list[str],
) -> dict:
    topic_mastery = build_topic_mastery(tag_counts)
    dsa_profile = build_dsa_profile(topic_mastery)
    blind_spots = detect_blind_spots(topic_mastery)
    interview_readiness = build_interview_readiness(topic_mastery)
    practice_habits = build_practice_habits(
        active_days_last_30, submissions_last_30, easy, medium, hard, attended_contests_count
    )
    difficulty_insight = build_difficulty_insight(easy, medium, hard)

    previous_topic_totals = (
        topic_totals(previous_tag_counts) if previous_tag_counts is not None else None
    )
    current_topic_totals = {t["topic"]: t["problems"] for t in topic_mastery}
    progress = build_progress(
        current_topic_totals, previous_topic_totals,
        total_solved, previous_total_solved,
        contest_rating, previous_contest_rating,
        new_skills,
    )

    return {
        "topic_mastery": topic_mastery,
        "dsa_profile": dsa_profile,
        "blind_spots": blind_spots,
        "interview_readiness": interview_readiness,
        "practice_habits": practice_habits,
        "difficulty_insight": difficulty_insight,
        "progress": progress,
        "skill_evidence_detail": {
            "reinforced": reinforced_skills,
            "new": new_skills,
            "unchanged": unchanged_skills,
        },
    }