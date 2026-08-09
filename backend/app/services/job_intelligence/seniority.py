# backend/app/services/job_intelligence/seniority.py
"""Stage 6 — seniority classification. Deterministic-first: a regex/
keyword scan for years-of-experience phrasing, scope language, and
title keywords. This module never calls an LLM itself — per the design
doc, an LLM refinement pass is only warranted when the deterministic
read is genuinely ambiguous, and that escalation is left as a documented
future extension point (kept out for now to avoid an unnecessary LLM
call on every single job analysis, matching the codebase's
graceful-cost-control philosophy elsewhere, e.g.
github_architecture_analyzer.py's quality-gated pass).
"""
import re

from app.schemas.job_intelligence import SeniorityLevel

_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:[-–to]{1,4}\s*(\d+))?\s*\+?\s*years?", re.IGNORECASE)

_TITLE_SIGNALS: dict[str, str] = {
    "intern": "intern",
    "new grad": "junior", "junior": "junior", "associate": "junior",
    "mid-level": "mid", "mid level": "mid",
    "staff": "staff", "principal": "staff",
    "lead": "senior", "senior": "senior", "sr.": "senior", "sr ": "senior",
}

_SCOPE_WORDS: dict[str, list[str]] = {
    "staff": ["own the roadmap", "cross-team", "staff-level", "architect the"],
    "senior": ["mentor", "drive technical decisions", "own the design", "lead the"],
}


def detect_seniority(raw_text: str, role_title: str | None) -> SeniorityLevel:
    lowered = raw_text.lower()
    title_lowered = (role_title or "").lower()
    evidence: list[str] = []
    level: str | None = None

    for signal, lvl in _TITLE_SIGNALS.items():
        if signal in title_lowered:
            level = lvl
            evidence.append(f"Title contains '{signal}'")
            break

    years_match = _YEARS_RE.search(lowered)
    if years_match:
        low = int(years_match.group(1))
        high = int(years_match.group(2)) if years_match.group(2) else low
        evidence.append(f"Years-of-experience phrase found ({low}-{high} years)")
        if level is None:
            if high <= 1:
                level = "junior"
            elif high <= 4:
                level = "mid"
            elif high <= 8:
                level = "senior"
            else:
                level = "staff"

    if level is None:
        for lvl, words in _SCOPE_WORDS.items():
            if any(w in lowered for w in words):
                level = lvl
                evidence.append(f"Scope language matched a '{lvl}' pattern")
                break

    if level is None:
        return SeniorityLevel(level="unspecified", evidence=[], confidence="low")

    confidence = "high" if len(evidence) >= 2 else "medium"
    return SeniorityLevel(level=level, evidence=evidence, confidence=confidence)