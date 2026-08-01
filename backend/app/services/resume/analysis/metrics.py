"""Module 5 — Metrics Analyzer.

Calculates "metric density" — the percentage of bullets that contain
at least one concrete number, percentage, or dollar amount. Deterministic;
zero LLM calls. Uses shared_signals.METRIC_PATTERN so this can never
disagree with bullet_analysis.py or ats_scorer_v2.py on whether a
bullet contains a metric.
"""
from app.services.resume.analysis.shared_signals import has_metric


def analyze_metrics(bullets: list[str]) -> dict:
    clean = [b.strip() for b in bullets if b.strip() and len(b.strip()) > 10]
    total = len(clean)

    if not total:
        return {
            "score": 0,
            "metric_density": 0,
            "bullets_with_metrics": 0,
            "bullets_without_metrics": 0,
            "total_bullets": 0,
        }

    with_metrics = sum(1 for b in clean if has_metric(b))
    without = total - with_metrics
    density = with_metrics / total * 100

    if density >= 70:
        score = 100
    elif density >= 55:
        score = 88 + (density - 55) * (12 / 15)
    elif density >= 40:
        score = 75 + (density - 40) * (13 / 15)
    elif density >= 25:
        score = 60 + (density - 25) * (15 / 15)
    else:
        score = max(15, density * 2.4)

    return {
        "score": round(score),
        "metric_density": round(density),
        "bullets_with_metrics": with_metrics,
        "bullets_without_metrics": without,
        "total_bullets": total,
    }