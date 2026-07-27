"""Score Aggregator — weighted average across all analysis modules."""

# Weights must sum to 1.0
WEIGHTS: dict[str, float] = {
    "content":    0.28,
    "structure":  0.20,
    "metrics":    0.15,
    "parsing":    0.14,
    "keywords":   0.10,
    "evidence":   0.08,
    "formatting": 0.05,
}


def compute_overall_score(module_scores: dict[str, int | float]) -> int:
    total = 0.0
    weight_sum = 0.0
    for key, weight in WEIGHTS.items():
        if key in module_scores:
            total      += module_scores[key] * weight
            weight_sum += weight
    return round(total / weight_sum) if weight_sum > 0 else 0


def get_grade(score: int) -> str:
    if score >= 93: return "A+"
    if score >= 90: return "A"
    if score >= 87: return "A-"
    if score >= 83: return "B+"
    if score >= 80: return "B"
    if score >= 77: return "B-"
    if score >= 73: return "C+"
    if score >= 70: return "C"
    if score >= 67: return "C-"
    if score >= 60: return "D"
    return "F"


def get_label(score: int) -> str:
    if score >= 90: return "Excellent"
    if score >= 80: return "Strong"
    if score >= 70: return "Good"
    if score >= 60: return "Fair"
    if score >= 50: return "Needs Work"
    return "Weak"


def get_grade_color(score: int) -> str:
    """Semantic color hint consumed by the frontend."""
    if score >= 80: return "success"
    if score >= 65: return "warning"
    return "danger"
