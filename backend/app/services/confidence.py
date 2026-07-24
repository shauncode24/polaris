WEIGHTS = {
    "project": 0.35,
    "experience": 0.25,
    "certificate": 0.15,
    "leetcode_tag": 0.10,
}
CONFIDENCE_CAP = 0.97


def compute_skill_confidence(evidence_weights: list[float]) -> float:
    return min(sum(evidence_weights), CONFIDENCE_CAP)
