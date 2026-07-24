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


def topic_totals(tag_counts: dict[str, int]) -> dict[str, int]:
    """Sums raw per-tag solved counts into per-canonical-topic totals.
    Topics with no matching tag in tag_counts still appear, at 0 —
    that's what makes blind-spot detection possible (§ blind_spots).
    """
    totals = {topic: 0 for topic in CANONICAL_TOPICS}
    for tag, count in tag_counts.items():
        topic = TAG_TO_TOPIC.get(tag)
        if topic is not None:
            totals[topic] += count
    return totals