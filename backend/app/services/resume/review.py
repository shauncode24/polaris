REVIEW_THRESHOLD = 0.3
PARTIAL_UPPER_THRESHOLD = 0.6


def flag_for_review(skill_name: str, confidence: float) -> dict | None:
    if confidence < REVIEW_THRESHOLD:
        return {"skill": skill_name, "confidence": confidence, "reason": "low evidence"}
    return None


def classify_match(confidence: float) -> str:
    """Three-way bucket for the Skill Gap Analyzer — replaces the old binary
    have-vs-missing split. A skill mentioned once in a single project shouldn't
    be treated identically to one backed by two projects and an internship
    bullet (Phase 4 enhancement doc, 'partial' category)."""
    if confidence < REVIEW_THRESHOLD:
        return "missing"
    if confidence < PARTIAL_UPPER_THRESHOLD:
        return "partial"
    return "have"