"""Deterministic per-bullet strength scoring. Detectors now come from
shared_signals.py so this can never disagree with content.py/metrics.py
about the same bullet.
"""
from app.services.resume.analysis.shared_signals import (
    has_metric,
    opens_with_strong_verb,
)
from app.services.resume.bullet_analysis import analyze_bullet

BASE_SCORE = 50
METRIC_BONUS = 25
STRONG_VERB_BONUS = 15
ISSUE_PENALTY = 8
MAX_EVIDENCE_BONUS = 20


def compute_bullet_strength(
    text: str,
    context_stack: list[str],
    skill_confidence_by_canonical: dict[str, float],
    resolved_stack_canonicals: list[str] | None = None,
) -> dict:
    issues = analyze_bullet(text)
    has_metric_flag = has_metric(text)
    strong_verb = opens_with_strong_verb(text)

    canonicals = resolved_stack_canonicals or []
    confidences = [skill_confidence_by_canonical[c] for c in canonicals if c in skill_confidence_by_canonical]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    score = BASE_SCORE
    if has_metric_flag:
        score += METRIC_BONUS
    if strong_verb:
        score += STRONG_VERB_BONUS
    score -= len(issues) * ISSUE_PENALTY
    score += avg_confidence * MAX_EVIDENCE_BONUS

    score = max(0, min(100, round(score)))

    return {
        "score": score,
        "issues": [i["type"] for i in issues],
        "has_metric": has_metric_flag,
        "strong_verb": strong_verb,
        "evidence_confidence": round(avg_confidence, 2),
    }