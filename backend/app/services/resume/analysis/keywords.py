"""Module 6 — Keyword Analyzer. Deterministic; zero LLM calls.
DEFAULT_SW_KEYWORDS now sources from shared_signals.TECH_KEYWORD_POOL so
this module and ats_scorer_v2.py can never disagree about which technical
terms exist in the vocabulary.
"""
import re

from app.services.resume.analysis.shared_signals import TECH_KEYWORD_POOL

DEFAULT_SW_KEYWORDS = TECH_KEYWORD_POOL  # kept as a name for backward compat


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _keyword_present(kw: str, norm_text: str) -> bool:
    escaped = re.escape(kw)
    return bool(re.search(r"(?<![a-zA-Z0-9#\+])" + escaped + r"(?![a-zA-Z0-9#\+])", norm_text))


def analyze_keywords(
    raw_text: str,
    jd_keywords: set[str] | None = None,
    profile_keywords: set[str] | None = None,
) -> dict:
    norm_text = _normalize(raw_text)

    if jd_keywords:
        keyword_pool = jd_keywords
    elif profile_keywords:
        keyword_pool = {k.lower() for k in profile_keywords if k}
    else:
        keyword_pool = DEFAULT_SW_KEYWORDS

    matched: list[str] = []
    missing: list[str] = []

    for kw in sorted(keyword_pool):
        if _keyword_present(kw, norm_text):
            matched.append(kw)
        else:
            missing.append(kw)

    total = len(keyword_pool)
    coverage = len(matched) / total * 100 if total else 0
    score = min(100, round(coverage * 1.25))

    return {
        "score": score,
        "matched": matched,
        "missing": missing[:20],
        "matched_count": len(matched),
        "missing_count": len(missing),
        "total_keywords": total,
        "coverage_pct": round(coverage),
        "using_default": jd_keywords is None,
    }