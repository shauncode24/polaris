"""Module 5 — Metrics Analyzer.

Calculates "metric density" — the percentage of bullets that contain
at least one concrete number, percentage, or dollar amount.
Deterministic; zero LLM calls.
"""
import re

# Matches: 35%, $50k, 3.5x, 15,000, 10M, 150+ etc.
_METRIC_RE = re.compile(
    r"(\b\d+(\.\d+)?\s*%"        # percentages: 35%, 3.5%
    r"|\$\s?\d[\d,\.]*[kKmMbB]?" # dollar amounts: $50, $1.2M, $500k
    r"|\b\d[\d,\.]*[kKmMbBxX]\b" # abbreviated: 10k, 5M, 3x
    r"|\b\d{2,}(?:,\d{3})*\b"    # large numbers: 15,000 or 1200
    r"|\b\d+\+)"                  # with plus: 150+
)


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

    with_metrics = sum(1 for b in clean if _METRIC_RE.search(b))
    without      = total - with_metrics
    density      = with_metrics / total * 100

    # Score curve:
    # ≥ 70% → 100   ≥ 55% → 88   ≥ 40% → 75   ≥ 25% → 60   < 25% → linear
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
