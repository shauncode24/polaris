# backend/app/services/leetcode/leetcode_taxonomy.py
"""Maps LeetCode's real tagSlug values (from tagProblemCounts in the
GraphQL response) to interview-relevant canonical topics.

Hardcoded, not LLM-derived — same reasoning as skill_classifier.py's
CANONICAL_SKILLS and github_taxonomy.py's TECH_CATEGORIES: this is a
small, stable vocabulary that doesn't need re-deriving per user.

A tag can only belong to one canonical topic here (no fan-out) so that
summing per-topic counts never double-counts a solved problem.
"""

CANONICAL_TOPICS: dict[str, list[str]] = {
    "Arrays & Hashing": ["array", "hash-table", "two-pointers", "prefix-sum", "counting"],
    "Strings": ["string", "string-matching"],
    "Sliding Window": ["sliding-window"],
    "Stack": ["stack", "monotonic-stack"],
    "Queue": ["queue", "monotonic-queue"],
    "Linked List": ["linked-list", "doubly-linked-list"],
    "Trees": ["tree", "binary-tree", "binary-search-tree"],
    "Graphs": ["graph", "depth-first-search", "breadth-first-search", "union-find", "topological-sort", "shortest-path"],
    "Heap": ["heap-priority-queue"],
    "Trie": ["trie"],
    "Dynamic Programming": ["dynamic-programming", "memoization"],
    "Greedy": ["greedy"],
    "Backtracking": ["backtracking"],
    "Bit Manipulation": ["bit-manipulation"],
    "Binary Search": ["binary-search"],
    "Intervals": ["interval"],
    "Sorting": ["sorting"],
    "Math": ["math", "number-theory", "combinatorics"],
    "Recursion": ["recursion", "divide-and-conquer"],
    "Design": ["design"],
}

# Reverse lookup, built once at import time: tag_slug -> canonical topic.
# Any tag not in this dict simply isn't part of the canonical-topic view
# (it still gets normal skill_evidence treatment elsewhere) — that's a
# deliberate scope boundary, not a bug: this taxonomy is for interview-DSA
# categories, not every LeetCode tag that exists.
TAG_TO_TOPIC: dict[str, str] = {
    tag: topic for topic, tags in CANONICAL_TOPICS.items() for tag in tags
}

# Difficulty-tier weighting for topic mastery — see leetcode_client.py's
# PROFILE_QUERY docstring for why "fundamental"/"intermediate"/"advanced"
# (LeetCode's own per-tag classification) is used as the difficulty proxy
# instead of per-problem Easy/Medium/Hard, which the unofficial API
# doesn't expose per tag. Weights are hand-set and explainable, same
# philosophy as skill_categories.py's TYPE_WEIGHTS: an advanced-tier solve
# should count for more toward mastery than a fundamental-tier one, but
# never by an amount that isn't easy to justify in one sentence.
TIER_WEIGHTS: dict[str, float] = {
    "fundamental": 1.0,
    "intermediate": 1.3,
    "advanced": 1.6,
}
DEFAULT_TIER_WEIGHT = 1.0  # unknown tier (e.g. manual entry with no tier data) -> no bonus, no penalty


def topic_totals(tag_counts: dict[str, int]) -> dict[str, int]:
    """Sums raw per-tag solved counts into per-canonical-topic totals.
    Topics with no matching tag in tag_counts still appear, at 0 —
    that's what makes blind-spot detection possible (§ blind_spots).
    This is the RAW, unweighted count — always shown to the user
    alongside the weighted mastery score, never replaced by it.
    """
    totals = {topic: 0 for topic in CANONICAL_TOPICS}
    for tag, count in tag_counts.items():
        topic = TAG_TO_TOPIC.get(tag)
        if topic is not None:
            totals[topic] += count
    return totals


def weighted_topic_totals(
    tag_counts: dict[str, int],
    tag_difficulty_tier: dict[str, str] | None = None,
) -> dict[str, float]:
    """Same rollup as topic_totals(), but each tag's contribution is
    multiplied by its difficulty-tier weight before summing. This is the
    basis for mastery LABELS (leetcode_mastery.py) — never for the raw
    "problems solved" count shown to the user, which always stays the
    real, unweighted number.
    """
    tag_difficulty_tier = tag_difficulty_tier or {}
    totals: dict[str, float] = {topic: 0.0 for topic in CANONICAL_TOPICS}
    for tag, count in tag_counts.items():
        topic = TAG_TO_TOPIC.get(tag)
        if topic is None:
            continue
        tier = tag_difficulty_tier.get(tag)
        weight = TIER_WEIGHTS.get(tier, DEFAULT_TIER_WEIGHT)
        totals[topic] += count * weight
    return {topic: round(value, 1) for topic, value in totals.items()}