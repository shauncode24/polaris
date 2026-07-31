"""Practice-diversity / anti-grind signal — deterministic, computed from
real tag-count deltas already available at sync time. Answers a question
consistency scoring alone can't: is practice spreading across topics, or
repeating the same comfortable ones? See LeetCode Module Review §2/§3D.
"""

REPEAT_SHARE_HIGH = 0.7
ALREADY_STRONG_FLOOR = 10  # roughly "Some Practice"+ per leetcode_mastery thresholds
MIN_SOLVES_FOR_GRINDING = 5  # avoid noisy flags on light sync cadences (e.g. 1 solve)


def compute_practice_diversity(
    current_topic_totals: dict[str, int],
    previous_topic_totals: dict[str, int] | None,
) -> dict:
    """current/previous_topic_totals: {canonical_topic: solved_count},
    already rolled up by leetcode_taxonomy.topic_totals(). Pure diff over
    real recorded totals — no LLM judgment.
    """
    previous_topic_totals = previous_topic_totals or {}

    newly_touched: list[str] = []
    reinforced_existing: list[str] = []
    deltas_by_topic: dict[str, int] = {}

    for topic, current_count in current_topic_totals.items():
        prev_count = previous_topic_totals.get(topic, 0)
        delta = current_count - prev_count
        if delta <= 0:
            continue
        deltas_by_topic[topic] = delta
        if prev_count == 0:
            newly_touched.append(topic)
        else:
            reinforced_existing.append(topic)

    total_new_solves = sum(deltas_by_topic.values())

    if total_new_solves == 0:
        return {
            "new_topics_touched": [],
            "reinforced_topics": [],
            "total_new_solves": 0,
            "diversity_ratio": None,
            "is_grinding": False,
            "message": "No new problems solved since the last sync — nothing to assess for diversity yet.",
        }

    already_strong_topics = {
        t for t, c in previous_topic_totals.items() if c >= ALREADY_STRONG_FLOOR
    }
    solves_in_already_strong = sum(
        delta for topic, delta in deltas_by_topic.items() if topic in already_strong_topics
    )
    repeat_share = solves_in_already_strong / total_new_solves
    is_grinding = (
        total_new_solves >= MIN_SOLVES_FOR_GRINDING
        and repeat_share >= REPEAT_SHARE_HIGH
        and len(newly_touched) == 0
    )

    diversity_ratio = round(len(newly_touched) / max(1, len(deltas_by_topic)), 2)

    if is_grinding:
        top_repeated = max(
            (t for t in deltas_by_topic if t in already_strong_topics),
            key=lambda t: deltas_by_topic[t],
            default=None,
        )
        message = (
            f"Most of your recent solving went toward {top_repeated}, a topic you're already "
            f"strong in. Consider spending some of that time on a topic you haven't touched yet."
        )
    elif newly_touched:
        message = f"Since your last sync you branched into {', '.join(newly_touched[:3])} — good breadth."
    else:
        message = "Recent practice is reinforcing existing topics rather than expanding into new ones."

    return {
        "new_topics_touched": sorted(newly_touched),
        "reinforced_topics": sorted(reinforced_existing),
        "total_new_solves": total_new_solves,
        "diversity_ratio": diversity_ratio,
        "is_grinding": is_grinding,
        "message": message,
    }