"""Module 4 — Content Analyzer.

Evaluates bullet quality: action verbs, passive voice, vague language,
length. Deterministic; zero LLM calls. Detectors are now imported from
shared_signals.py so this module can never disagree with bullet_strength.py
or ats_scorer_v2.py about whether a given bullet has a metric or opens
with a strong verb.
"""
from app.services.resume.bullet_analysis import analyze_bullet
from app.services.resume.analysis.shared_signals import (
    STRONG_ACTION_VERBS,   # re-exported for callers that still import from here
    opens_with_strong_verb,
    has_filler,
)


def analyze_content(bullets: list[str]) -> dict:
    clean = [b.strip() for b in bullets if b.strip() and len(b.strip()) > 10]
    total = len(clean)

    if not total:
        return {
            "score": 0,
            "total_bullets": 0,
            "flagged_count": 0,
            "strong_verb_count": 0,
            "strong_verb_pct": 0,
            "filler_count": 0,
            "issue_type_counts": {},
            "flagged_bullets": [],
        }

    strong_verb_count = 0
    filler_count = 0
    flagged_bullets: list[dict] = []
    all_issues: list[dict] = []

    for bullet in clean:
        if opens_with_strong_verb(bullet):
            strong_verb_count += 1
        if has_filler(bullet):
            filler_count += 1

        issues = analyze_bullet(bullet)
        if issues:
            flagged_bullets.append({
                "text": (bullet[:120] + "…") if len(bullet) > 120 else bullet,
                "issues": [i["type"] for i in issues],
            })
            all_issues.extend(issues)

    flagged_count = len(flagged_bullets)
    strong_verb_pct = round(strong_verb_count / total * 100)

    flag_penalty = (flagged_count / total) * 55
    filler_penalty = (filler_count / total) * 15
    score = max(0, 100 - flag_penalty - filler_penalty)

    type_counts: dict[str, int] = {}
    for issue in all_issues:
        t = issue["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "score": round(score),
        "total_bullets": total,
        "flagged_count": flagged_count,
        "strong_verb_count": strong_verb_count,
        "strong_verb_pct": strong_verb_pct,
        "filler_count": filler_count,
        "issue_type_counts": type_counts,
        "flagged_bullets": flagged_bullets[:12],
    }