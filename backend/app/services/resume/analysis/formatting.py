"""Module 3 — Formatting Analyzer.

Checks visual consistency: bullet style, line length, date formats.
Deterministic; zero LLM calls.
"""
import re

_BULLET_START_RE = re.compile(r"^[\-\*\•\–\—◦▸►▪]")
_ABBREV_MONTH_RE = re.compile(r"\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b")
_FULL_MONTH_RE   = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b")
_DATE_RANGE_RE   = re.compile(r"\b(19|20)\d{2}\s*[-–]\s*((19|20)\d{2}|Present|Current|Now)\b", re.IGNORECASE)


def analyze_formatting(raw_text: str) -> dict:
    issues: list[dict] = []
    lines = [l for l in raw_text.split("\n") if l.strip()]

    # --- Bullet style consistency ---
    bullet_lines = [l.strip() for l in lines if _BULLET_START_RE.match(l.strip())]
    if bullet_lines:
        starters = {l[0] for l in bullet_lines if l}
        if len(starters) > 2:
            issues.append({
                "type": "inconsistent_bullets",
                "severity": "low",
                "detail": f"Using {len(starters)} different bullet characters ({', '.join(sorted(starters))}). Pick one style and use it everywhere.",
            })

    # --- Excessively long lines (walls of text) ---
    long_lines = [l for l in lines if len(l.strip()) > 200]
    if len(long_lines) > 3:
        issues.append({
            "type": "long_lines",
            "severity": "low",
            "detail": f"{len(long_lines)} lines exceed 200 characters. Prefer concise bullets over dense paragraphs.",
        })

    # --- Orphaned short fragments (usually a PDF extraction artifact) ---
    orphan_lines = [l for l in lines if 1 <= len(l.strip().split()) <= 2 and l.strip().isalpha() and len(l.strip()) > 3]
    if len(orphan_lines) > 4:
        issues.append({
            "type": "orphan_fragments",
            "severity": "low",
            "detail": "Detected several isolated single/double-word lines — possible formatting artifacts or layout breaks.",
        })

    # --- Date format consistency ---
    abbrev_count = len(_ABBREV_MONTH_RE.findall(raw_text))
    full_count   = len(_FULL_MONTH_RE.findall(raw_text))
    if abbrev_count > 0 and full_count > 0:
        issues.append({
            "type": "inconsistent_dates",
            "severity": "low",
            "detail": "Mix of abbreviated and full month names (e.g. 'Jan' vs 'January'). Standardize for consistency.",
        })

    # --- Score ---
    score = max(0, 100 - len(issues) * 8)

    return {
        "score": round(score),
        "bullet_styles_used": sorted({l[0] for l in bullet_lines if l}) if bullet_lines else [],
        "issues": issues,
    }
