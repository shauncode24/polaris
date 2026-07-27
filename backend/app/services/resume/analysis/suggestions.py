"""Suggestions Engine.

Converts raw module outputs into a prioritised, human-readable list of
action items. Every suggestion has a priority (high / medium / low),
the module it came from, a title, a detail explanation, and the
expected impact.

No LLM calls — pure rule engine.
"""
from __future__ import annotations

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _s(priority: str, module: str, title: str, detail: str, impact: str) -> dict:
    return {"priority": priority, "module": module, "title": title, "detail": detail, "impact": impact}


def generate_suggestions(
    structure:  dict,
    parsing:    dict,
    formatting: dict,
    content:    dict,
    metrics:    dict,
    keywords:   dict,
    evidence:   dict,
) -> list[dict]:
    suggestions: list[dict] = []

    # ── HIGH ─────────────────────────────────────────────────────────────────

    if not parsing.get("has_email"):
        suggestions.append(_s(
            "high", "parsing",
            "Add your email address",
            "No email address was detected. This is critical for ATS systems and recruiters.",
            "Without an email, recruiters cannot contact you and ATS may auto-reject the resume.",
        ))

    for sec in structure.get("missing_required", []):
        suggestions.append(_s(
            "high", "structure",
            f"Add a '{sec.title()}' section",
            f"The '{sec.title()}' section is missing — it's required by most ATS systems and expected by every recruiter.",
            "Missing required sections lower ATS match scores and confuse resume parsers.",
        ))

    density = metrics.get("metric_density", 100)
    no_metric = metrics.get("bullets_without_metrics", 0)
    if density < 30 and no_metric > 0:
        suggestions.append(_s(
            "high", "metrics",
            f"Add numbers to {no_metric} bullets",
            f"Only {density}% of bullets contain a measurable metric (%, $, users, ms, etc.). "
            "Quantified impact is the single biggest differentiator between weak and strong resumes.",
            "Quantified resumes are ~40% more likely to pass recruiter screening.",
        ))

    weak_verb_count = content.get("issue_type_counts", {}).get("weak_verb", 0)
    if weak_verb_count > 3:
        suggestions.append(_s(
            "high", "content",
            f"Replace weak openers in {weak_verb_count} bullets",
            "Bullets that open with 'worked on', 'responsible for', or 'helped with' signal lack of "
            "ownership. Replace with strong action verbs like 'Built', 'Designed', 'Automated'.",
            "Recruiters spend ~7 seconds per resume — strong action verbs catch and hold attention.",
        ))

    # ── MEDIUM ────────────────────────────────────────────────────────────────

    if 30 <= density < 55 and no_metric > 0:
        suggestions.append(_s(
            "medium", "metrics",
            f"Add metrics to {no_metric} more bullets",
            f"Only {density}% of bullets have numbers. Aim for 60-70%+ to demonstrate clear impact.",
            "Impact quantification is the fastest way to make a resume more compelling.",
        ))

    if 1 <= weak_verb_count <= 3:
        suggestions.append(_s(
            "medium", "content",
            f"Replace weak openers in {weak_verb_count} bullets",
            "Bullets that open with 'worked on', 'helped', or 'participated in' weaken your ownership narrative.",
            "Active, strong verbs show initiative and direct contribution.",
        ))

    passive_count = content.get("issue_type_counts", {}).get("passive_voice", 0)
    if passive_count > 0:
        suggestions.append(_s(
            "medium", "content",
            f"Rewrite {passive_count} passive-voice bullets",
            "Passive voice ('was built', 'was designed') hides your direct contribution. "
            "Rewrite to make yourself the subject: 'Built X', 'Designed Y'.",
            "Active voice communicates ownership and decision-making authority.",
        ))

    for sec in structure.get("missing_recommended", []):
        suggestions.append(_s(
            "medium", "structure",
            f"Add a '{sec.title()}' section",
            f"A '{sec.title()}' section is strongly recommended but not detected in your resume.",
            "Completeness signals professionalism and helps recruiters form a fuller picture.",
        ))

    coverage = keywords.get("coverage_pct", 100)
    missing_kw = keywords.get("missing", [])
    if coverage < 60 and missing_kw:
        top = ", ".join(missing_kw[:5])
        suggestions.append(_s(
            "medium", "keywords",
            "Add missing technical keywords",
            f"Keywords not found in your resume: {top}. "
            "If you have experience with any of these, mention them explicitly.",
            "ATS filters resumes by keyword presence before a human reads them.",
        ))

    low_ev = evidence.get("low_confidence", 0)
    if low_ev > 1:
        suggestions.append(_s(
            "medium", "evidence",
            f"Back up {low_ev} skills with real examples",
            f"{low_ev} skills listed in your resume have no supporting evidence in your projects or experience bullets.",
            "Unsubstantiated skills reduce recruiter confidence and can backfire in interviews.",
        ))

    too_short = content.get("issue_type_counts", {}).get("too_short", 0)
    if too_short > 0:
        suggestions.append(_s(
            "medium", "content",
            f"Expand {too_short} underdeveloped bullets",
            f"{too_short} bullets are under 30 characters — likely missing context or impact.",
            "Each bullet should describe what you did, how, and with what result.",
        ))

    # ── LOW ───────────────────────────────────────────────────────────────────

    if not parsing.get("has_phone"):
        suggestions.append(_s(
            "low", "parsing",
            "Add your phone number",
            "No phone number detected. Some recruiters prefer calling candidates directly.",
            "Easy to add; increases recruiter reach options.",
        ))

    if not parsing.get("has_linkedin"):
        suggestions.append(_s(
            "low", "parsing",
            "Add your LinkedIn URL",
            "No LinkedIn URL detected. Most recruiters verify candidates on LinkedIn before reaching out.",
            "Easier recruiter validation and professional credibility signal.",
        ))

    for issue in formatting.get("issues", []):
        if issue["severity"] == "low":
            suggestions.append(_s(
                "low", "formatting",
                f"Formatting: {issue['detail'][:70]}",
                issue["detail"],
                "Consistent formatting improves readability and ATS parsing reliability.",
            ))

    too_long_bullets = content.get("issue_type_counts", {}).get("too_long", 0)
    if too_long_bullets > 0:
        suggestions.append(_s(
            "low", "content",
            f"Tighten {too_long_bullets} overlong bullets",
            f"{too_long_bullets} bullets exceed 260 characters. Tighten them for scannability.",
            "Recruiters skim; shorter, punchier bullets have higher read rates.",
        ))

    # Sort high → medium → low
    suggestions.sort(key=lambda s: _PRIORITY_ORDER.get(s["priority"], 3))
    return suggestions
