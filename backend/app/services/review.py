REVIEW_THRESHOLD = 0.3


def flag_for_review(skill_name: str, confidence: float) -> dict | None:
    if confidence < REVIEW_THRESHOLD:
        return {"skill": skill_name, "confidence": confidence, "reason": "low evidence"}
    return None