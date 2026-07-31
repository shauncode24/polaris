WEIGHTS = {
    "project": 0.35,
    "github": 0.30,
    "experience": 0.25,
    "certificate": 0.15,
    "leetcode_tag": 0.10,
}
CONFIDENCE_CAP = 0.97


def compute_skill_confidence(evidence_weights: list[float]) -> float:
    return min(sum(evidence_weights), CONFIDENCE_CAP)


def compute_decayed_skill_confidence(evidence_rows: list) -> float:
    """Recency-aware version of compute_skill_confidence for callers that
    already have persisted SkillEvidence rows (with a created_at) in
    hand — jobs/gap_analysis.py, career_planner/context_builder.py,
    interview/context_builder.py, and evidence.get_all_skill_confidences
    all use this instead of the raw weight-sum version, so confidence
    reflects how current the evidence is, not just whether it was ever
    true once. ingestion.py's confidence computation (evidence being
    created right now, this instant) is unaffected — freshly created
    evidence decays to a 1.0 multiplier trivially, so it's left as-is.
    """
    from app.services.resume.decay import decay_multiplier
    decayed_weights = [e.weight * decay_multiplier(getattr(e, "created_at", None)) for e in evidence_rows]
    return compute_skill_confidence(decayed_weights)