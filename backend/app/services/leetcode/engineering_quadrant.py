"""Engineering Maturity Quadrant — the highest-value cross-module
inference from the LeetCode Module Review (§5). Fuses a normalized
LeetCode algorithmic-mastery score with a normalized GitHub practical-
engineering score into one of four quadrants. Fully deterministic; the
LLM (leetcode_reviewer.py) only narrates the placement, never decides it.
"""

# Normalized mastery score for QUADRANT CLASSIFICATION only — maps labels
# to a 0-1 scale used to compute a single per-user LeetCode score (0-100)
# that is compared against a STRONG_THRESHOLD. These values are NOT shared
# with company_readiness.py, which uses a different scale (0.0-1.0 as a
# weighted-average readiness %) for a completely different computation.
# Having two maps is intentional: they answer different questions.
MASTERY_SCORE_MAP = {
    "Not Practiced": 0.0, "Introduced": 0.25, "Some Practice": 0.5,
    "Consistent Practice": 0.8, "Extensive Practice": 1.0,
}
STRONG_THRESHOLD = 55  # 0-100 scale


def compute_leetcode_score(topic_mastery: list[dict]) -> float:
    if not topic_mastery:
        return 0.0
    scores = [MASTERY_SCORE_MAP.get(t["mastery"], 0.0) for t in topic_mastery]
    return round((sum(scores) / len(scores)) * 100, 1)


def compute_github_score(repositories: list[dict]) -> float:
    """Average of (quality_score * 0.6 + activity_score * 0.4) across
    synced repos — same weighting github_knowledge.py already uses to
    rank repos, just averaged instead of used for sorting.
    """
    scored = [
        r for r in repositories
        if r.get("quality_score") is not None and r.get("activity_score") is not None
    ]
    if not scored:
        return 0.0
    combined = [r["quality_score"] * 0.6 + r["activity_score"] * 0.4 for r in scored]
    return round(sum(combined) / len(combined), 1)


def classify_quadrant(leetcode_score: float, github_score: float) -> dict:
    leetcode_strong = leetcode_score >= STRONG_THRESHOLD
    github_strong = github_score >= STRONG_THRESHOLD

    if leetcode_strong and github_strong:
        label = "Well-Rounded"
        description = (
            "Strong evidence on both algorithmic reasoning and practical engineering — "
            "a genuinely differentiated profile for most interview loops."
        )
    elif github_strong and not leetcode_strong:
        label = "Builder"
        description = (
            "Practical engineering evidence is stronger than algorithmic-interview evidence "
            "right now. Likely to do well in system-design/project-heavy loops, and at higher "
            "risk in pure DSA rounds."
        )
    elif leetcode_strong and not github_strong:
        label = "Solver"
        description = (
            "Algorithmic problem-solving evidence is stronger than the practical engineering "
            "portfolio right now. Likely to clear DSA-heavy rounds, and at higher risk in "
            "'walk me through a project' or system-design conversations."
        )
    else:
        label = "Foundational"
        description = (
            "Both algorithmic and practical-engineering evidence are still early. Worth "
            "sequencing both tracks deliberately rather than over-indexing on either alone."
        )

    return {"label": label, "description": description}


def compute_engineering_quadrant(topic_mastery: list[dict], repositories: list[dict]) -> dict:
    leetcode_score = compute_leetcode_score(topic_mastery)
    github_score = compute_github_score(repositories)
    classification = classify_quadrant(leetcode_score, github_score)

    return {
        "leetcode_score": leetcode_score,
        "github_score": github_score,
        "quadrant_label": classification["label"],
        "description": classification["description"],
    }