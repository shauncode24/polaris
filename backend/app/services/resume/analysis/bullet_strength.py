"""Deterministic per-bullet strength scoring — the missing "which bullets
are actually carrying the resume" signal. Combines primitives that
already exist (analyze_bullet's issue flags, the metric regex, the
strong-action-verb set, and per-skill evidence confidence) into one
comparable number per bullet. This is a ranking signal for dilution
detection and tailoring, not a standalone quality grade — an LLM never
decides this number, same boundary as resume/confidence.py's formula.
"""
from app.services.resume.analysis.content import STRONG_ACTION_VERBS, _FIRST_WORD_RE
from app.services.resume.bullet_analysis import _METRIC_PATTERN, analyze_bullet

BASE_SCORE = 50
METRIC_BONUS = 25
STRONG_VERB_BONUS = 15
ISSUE_PENALTY = 8
MAX_EVIDENCE_BONUS = 20


def _opens_with_strong_verb(text: str) -> bool:
    m = _FIRST_WORD_RE.match(text.strip())
    return bool(m) and m.group(1).lower() in STRONG_ACTION_VERBS


def compute_bullet_strength(
    text: str,
    context_stack: list[str],
    skill_confidence_by_canonical: dict[str, float],
    resolved_stack_canonicals: list[str] | None = None,
) -> dict:
    """Returns {"score": int 0-100, "issues": [...], "has_metric": bool,
    "strong_verb": bool, "evidence_confidence": float}.
    """
    issues = analyze_bullet(text)
    has_metric = bool(_METRIC_PATTERN.search(text))
    strong_verb = _opens_with_strong_verb(text)

    canonicals = resolved_stack_canonicals or []
    confidences = [skill_confidence_by_canonical[c] for c in canonicals if c in skill_confidence_by_canonical]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    score = BASE_SCORE
    if has_metric:
        score += METRIC_BONUS
    if strong_verb:
        score += STRONG_VERB_BONUS
    score -= len(issues) * ISSUE_PENALTY
    score += avg_confidence * MAX_EVIDENCE_BONUS

    score = max(0, min(100, round(score)))

    return {
        "score": score,
        "issues": [i["type"] for i in issues],
        "has_metric": has_metric,
        "strong_verb": strong_verb,
        "evidence_confidence": round(avg_confidence, 2),
    }