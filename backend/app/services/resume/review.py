from app.services.resume.confidence_thresholds import gap_label_for_confidence, medium_floor

# Was a hardcoded 0.3 — now derived from the ONE canonical confidence
# table (confidence_thresholds.py), so this can never silently drift
# from role_fit's or the skill-gap classifier's own cutoffs again.
REVIEW_THRESHOLD = medium_floor()


def flag_for_review(skill_name: str, confidence: float) -> dict | None:
    if confidence < REVIEW_THRESHOLD:
        return {"skill": skill_name, "confidence": confidence, "reason": "low evidence"}
    return None


def classify_match(confidence: float) -> str:
    """Three-way bucket for the Skill Gap Analyzer — replaces the old binary
    have-vs-missing split. Delegates entirely to the single canonical
    confidence table instead of its own hardcoded cutoffs (Engineering
    Identity fix #1) — this is now structurally impossible to disagree
    with role_fit's labeling."""
    return gap_label_for_confidence(confidence)