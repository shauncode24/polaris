"""Canonical confidence-bucket thresholds — Engineering Identity fix #1.

The ONLY "confidence" number in this codebase is the numeric, recency-
decayed evidence score from resume/confidence.py + resume/decay.py
(0.0 - CONFIDENCE_CAP). Before this module existed, three places turned
that number — or a totally different number — into a label with three
different cutoffs:
  - resume/analysis/role_fit.py's get_confident_canonical_skills: 0.5 / 0.15
  - resume/review.py's classify_match (skill-gap have/partial/missing): 0.3 / 0.6
  - resume/analysis/evidence.py's analyze_evidence: a SEPARATE signal
    entirely (source count, not the decayed score) that happened to also
    be called "confidence" — see that module's rename to
    "corroboration_level"/"corroboration_count".

This module is now the single place that owns the score->label mapping.
Anything that needs a label from the canonical decayed confidence score
imports from here — never hardcodes its own cutoffs again.
"""

# (floor, label), descending order — label applies once score >= floor.
CONFIDENCE_BUCKETS: list[tuple[float, str]] = [
    (0.6, "high"),
    (0.3, "medium"),
    (0.0, "low"),
]

# Skill-gap vocabulary (have/partial/missing) maps onto the SAME floors
# as CONFIDENCE_BUCKETS — a "high" confidence skill is always a "have"
# skill and a "low" one is always "missing". No separate cutoffs exist
# anywhere else in the codebase after this fix.
GAP_ANALYSIS_LABELS: dict[str, str] = {"high": "have", "medium": "partial", "low": "missing"}


def label_for_confidence(score: float) -> str:
    for floor, label in CONFIDENCE_BUCKETS:
        if score >= floor:
            return label
    return CONFIDENCE_BUCKETS[-1][1]


def gap_label_for_confidence(score: float) -> str:
    return GAP_ANALYSIS_LABELS[label_for_confidence(score)]


def medium_floor() -> float:
    """The 'medium' floor — resume/review.py's REVIEW_THRESHOLD and the
    skill-gap 'missing' cutoff must both equal this. Exposed as a function
    (rather than relying on callers to index CONFIDENCE_BUCKETS directly)
    so the intent is explicit at each call site."""
    return next(floor for floor, label in CONFIDENCE_BUCKETS if label == "medium")


def high_floor() -> float:
    return next(floor for floor, label in CONFIDENCE_BUCKETS if label == "high")