"""Engineering Maturity Quadrant — the highest-value cross-module
inference from the LeetCode Module Review (§5). Fuses a normalized
LeetCode algorithmic-mastery score with a normalized GitHub practical-
engineering score into one of four quadrants. Fully deterministic; the
LLM (leetcode_reviewer.py) only narrates the placement, never decides it.
"""

from app.services.leetcode.leetcode_mastery import MASTERY_SCORE_BASE
from app.services.leetcode.company_readiness import COMPANY_TOPIC_WEIGHTS
from app.services.leetcode.leetcode_taxonomy import CANONICAL_TOPICS

# Quadrant classification uses the BASE scale unmodified — see
# leetcode_mastery.MASTERY_SCORE_BASE's docstring for why this file and
# company_readiness.py intentionally read from the same source with only
# one documented divergence (company_readiness's credit bump).
MASTERY_SCORE_MAP = MASTERY_SCORE_BASE
STRONG_THRESHOLD = 55  # 0-100 scale
DEFAULT_TOPIC_IMPORTANCE = 0.3  # topics absent from every company profile still count, just lightly

def _general_topic_importance() -> dict[str, float]:
    """Average importance weight for each canonical topic across every
    company/tier profile in COMPANY_TOPIC_WEIGHTS. This is deliberately a
    GENERAL, cross-company signal — distinct from company_readiness.py's
    PER-company weighting, which answers a different, more specific
    question ("ready for Amazon specifically" vs "broadly interview-ready").
    Topics that don't appear in any company's profile still get a small
    DEFAULT_TOPIC_IMPORTANCE rather than 0, since real interview loops
    outside the hand-seeded company list exist. Computed once at import
    time since COMPANY_TOPIC_WEIGHTS is static, hand-seeded data.
    """
    sums: dict[str, float] = {t: 0.0 for t in CANONICAL_TOPICS}
    counts: dict[str, int] = {t: 0 for t in CANONICAL_TOPICS}
    for weights in COMPANY_TOPIC_WEIGHTS.values():
        for topic, w in weights.items():
            sums[topic] += w
            counts[topic] += 1
    return {
        topic: (sums[topic] / counts[topic] if counts[topic] > 0 else DEFAULT_TOPIC_IMPORTANCE)
        for topic in CANONICAL_TOPICS
    }


GENERAL_TOPIC_IMPORTANCE = _general_topic_importance()


def compute_leetcode_score(topic_mastery: list[dict]) -> float:
    """Importance-weighted average, not a flat average across all 19
    topics — a topic that matters across most real interview loops (e.g.
    Arrays & Hashing, Trees) now moves this score more than a rarely-
    tested one (e.g. Trie), fixing the "too loose" quadrant classification
    flagged in the module audit, while staying distinct from
    company_readiness.py's per-company weighting.
    """
    if not topic_mastery:
        return 0.0
    weighted_sum = weight_total = 0.0
    for t in topic_mastery:
        importance = GENERAL_TOPIC_IMPORTANCE.get(t["topic"], DEFAULT_TOPIC_IMPORTANCE)
        weighted_sum += MASTERY_SCORE_MAP.get(t["mastery"], 0.0) * importance
        weight_total += importance
    return round((weighted_sum / weight_total) * 100, 1) if weight_total > 0 else 0.0


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