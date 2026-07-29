"""Solo-vs-collaborative signal — deterministic, from real PR/review
counts. Answers a question no other module captures: was this built in
isolation, or with review feedback from other people. Cheap and
explainable, same philosophy as github_scoring.py.
"""

MIN_PRS_FOR_COLLABORATIVE = 5
MIN_REVIEW_RATE_FOR_COLLABORATIVE = 0.3


def score_collaboration(pr_count: int, reviewed_pr_count: int) -> dict:
    if pr_count == 0:
        return {"mode": "solo", "score": 0, "pr_count": 0, "reviewed_pr_count": 0}

    review_rate = reviewed_pr_count / pr_count
    score = min(pr_count, 20) / 20 * 50 + review_rate * 50

    if pr_count >= MIN_PRS_FOR_COLLABORATIVE and review_rate >= MIN_REVIEW_RATE_FOR_COLLABORATIVE:
        mode = "collaborative"
    elif pr_count >= 1:
        mode = "mixed"
    else:
        mode = "solo"

    return {
        "mode": mode,
        "score": round(score),
        "pr_count": pr_count,
        "reviewed_pr_count": reviewed_pr_count,
    }