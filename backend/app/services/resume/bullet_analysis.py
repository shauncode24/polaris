import re

WEAK_OPENERS = {
    "helped", "worked on", "responsible for", "assisted", "involved in",
    "tasked with", "participated in", "in charge of", "duties included",
    "worked with", "familiar with",
}

_METRIC_PATTERN = re.compile(r"(\d+(\.\d+)?\s*%|\$\s?\d|\b\d+(\.\d+)?[kKmMxX]?\b)")
_PASSIVE_PATTERN = re.compile(r"\b(was|were|been|being|is|are)\s+\w+ed\b", re.IGNORECASE)

MIN_BULLET_LEN = 30
MAX_BULLET_LEN = 260


def _starts_with_weak_opener(text: str) -> bool:
    lowered = text.strip().lower()
    return any(lowered.startswith(opener) for opener in WEAK_OPENERS)


def analyze_bullet(text: str) -> list[dict]:
    """Rule-based, deterministic bullet analysis — same philosophy as
    resume/confidence.py: anything reliably computable in code should
    never be left to LLM judgment, especially something as checkable as
    'does this contain a number'. Returns a list of issue dicts, empty
    if the bullet is clean.
    """
    issues: list[dict] = []
    stripped = text.strip()

    if not stripped:
        return issues

    if not _METRIC_PATTERN.search(stripped):
        issues.append({
            "type": "missing_metric",
            "detail": "No quantified metric (number, %, or $) found in this bullet.",
        })

    if _starts_with_weak_opener(stripped):
        issues.append({
            "type": "weak_verb",
            "detail": "Bullet opens with a weak/passive phrase instead of a strong action verb.",
        })

    if _PASSIVE_PATTERN.search(stripped):
        issues.append({
            "type": "passive_voice",
            "detail": "Bullet appears to use passive voice.",
        })

    if len(stripped) < MIN_BULLET_LEN:
        issues.append({
            "type": "too_short",
            "detail": f"Bullet is only {len(stripped)} characters — likely lacks enough context/impact.",
        })
    elif len(stripped) > MAX_BULLET_LEN:
        issues.append({
            "type": "too_long",
            "detail": f"Bullet is {len(stripped)} characters — consider tightening it.",
        })

    return issues