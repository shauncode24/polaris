"""Company-specific interview readiness mapping — deterministic pattern
match of real topic_mastery against a hand-seeded weight table, same
philosophy as career_planner/curriculum.py's DOMAIN_CURRICULA. The LLM
never decides these weights or scores; it only narrates them. See
LeetCode Module Review §3B.
"""

# canonical_topic (from leetcode_taxonomy.CANONICAL_TOPICS) -> importance
# weight (0-1) for that company/tier's typical interview loop. Hand-seeded,
# not scraped or user-specific. Extend by hand over time.
COMPANY_TOPIC_WEIGHTS: dict[str, dict[str, float]] = {
    "Amazon": {
        "Graphs": 0.9, "Trees": 0.8, "Arrays & Hashing": 0.6,
        "Dynamic Programming": 0.5, "Design": 0.6, "Backtracking": 0.3,
    },
    "Google": {
        "Graphs": 0.8, "Dynamic Programming": 0.8, "Trees": 0.7,
        "Arrays & Hashing": 0.6, "Backtracking": 0.6, "Math": 0.5, "Design": 0.4,
    },
    "Meta": {
        "Arrays & Hashing": 0.8, "Trees": 0.7, "Graphs": 0.6,
        "Strings": 0.6, "Dynamic Programming": 0.5, "Binary Search": 0.5,
    },
    "Microsoft": {
        "Trees": 0.7, "Arrays & Hashing": 0.7, "Linked List": 0.6,
        "Dynamic Programming": 0.5, "Design": 0.5, "Strings": 0.5,
    },
    "Startup / Product Company": {
        "Arrays & Hashing": 0.5, "Strings": 0.4, "Design": 0.5,
        "Trees": 0.3, "Dynamic Programming": 0.2, "Graphs": 0.2,
    },
    "Trading / Quant (e.g. Tower Research)": {
        "Dynamic Programming": 0.8, "Math": 0.8, "Graphs": 0.6,
        "Bit Manipulation": 0.6, "Greedy": 0.5, "Binary Search": 0.5,
    },
}

MASTERY_SCORE_MAP = {
    "Not Practiced": 0.0, "Introduced": 0.3, "Some Practice": 0.6,
    "Consistent Practice": 0.85, "Extensive Practice": 1.0,
}
WEAK_FLOOR = 0.6


def compute_company_readiness(topic_mastery: list[dict]) -> list[dict]:
    """topic_mastery: leetcode_insights.build_topic_mastery() output.
    Returns one entry per company/tier, sorted strongest-first, each with
    a real recomputable 0-100 weighted-average readiness score and the
    specific weak topics dragging it down.
    """
    mastery_by_topic = {t["topic"]: t["mastery"] for t in topic_mastery}

    results = []
    for company, weights in COMPANY_TOPIC_WEIGHTS.items():
        weighted_sum = weight_total = 0.0
        weak_topics = []

        for topic, weight in weights.items():
            mastery_label = mastery_by_topic.get(topic, "Not Practiced")
            score = MASTERY_SCORE_MAP.get(mastery_label, 0.0)
            weighted_sum += score * weight
            weight_total += weight
            if score < WEAK_FLOOR:
                weak_topics.append(topic)

        readiness_pct = round((weighted_sum / weight_total) * 100) if weight_total > 0 else 0
        weak_topics_sorted = sorted(weak_topics, key=lambda t: weights.get(t, 0), reverse=True)

        results.append({
            "company": company,
            "readiness_pct": readiness_pct,
            "weak_topics": weak_topics_sorted[:3],
        })

    return sorted(results, key=lambda r: r["readiness_pct"], reverse=True)