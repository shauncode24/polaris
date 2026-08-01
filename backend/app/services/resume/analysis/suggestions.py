"""Suggestions Engine.

Converts raw module outputs into a prioritised, human-readable list of
action items. No LLM calls — pure rule engine.

FIX (Critical #1): `ats_warnings` (the canonical v2 warnings — the same
ones that produced the displayed overall_score) are now folded in
directly, so a "missing email" or "missing experience section" warning
can never appear in the score's warnings list without also appearing as
a suggestion, and vice versa. The content/metrics/keywords module scores
are still used for fine-grained per-bullet suggestions, but since they
now share detectors with ats_scorer_v2 (shared_signals.py), they can no
longer disagree with it about whether a given signal is present.
"""
from __future__ import annotations

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

_WARNING_SUGGESTION_COPY: dict[str, tuple[str, str]] = {
    # warning type -> (title, impact)
    "missing_email": ("Add a contact email address", "ATS and recruiters require a reachable email."),
    "missing_phone": ("Add a phone number", "Recruiters often prefer a direct line for scheduling."),
    "missing_github": ("Add your GitHub profile link", "Lets reviewers verify real project work."),
    "missing_linkedin": ("Add your LinkedIn profile link", "Most recruiters cross-check candidates on LinkedIn."),
    "missing_experience": ("Add at least one experience entry", "An experience section is expected by most ATS parsers."),
    "missing_projects": ("Add a projects section", "Projects section strengthens technical credibility."),
    "missing_education": ("Add an education section", "Most ATS systems expect an education section."),
    "encoding_issues": ("Fix non-ASCII / encoding artifacts", "Odd characters can break ATS parsing on some platforms."),
    "fancy_bullets": ("Replace fancy Unicode bullets with plain hyphens", "Some ATS parsers misread stylized bullet glyphs."),
}


def _s(priority: str, module: str, title: str, detail: str, impact: str) -> dict:
    return {"priority": priority, "module": module, "title": title, "detail": detail, "impact": impact}


def _suggestions_from_ats_warnings(ats_warnings: list[dict]) -> list[dict]:
    out = []
    for w in ats_warnings:
        copy = _WARNING_SUGGESTION_COPY.get(w["type"])
        if copy is None:
            continue
        title, impact = copy
        out.append(_s(w["severity"], "ats", title, w["detail"], impact))
    return out


def generate_suggestions(
    structure:  dict,
    parsing:    dict,
    formatting: dict,
    content:    dict,
    metrics:    dict,
    keywords:   dict,
    evidence:   dict,
    ats_warnings: list[dict] | None = None,
) -> list[dict]:
    suggestions: list[dict] = []

    # ── Canonical ATS warnings (same source as the displayed score) ────────
    if ats_warnings:
        suggestions.extend(_suggestions_from_ats_warnings(ats_warnings))

    # ── HIGH ─────────────────────────────────────────────────────────────

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

    # ── MEDIUM ────────────────────────────────────────────────────────────

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

    # ── LOW ───────────────────────────────────────────────────────────────

    too_long_bullets = content.get("issue_type_counts", {}).get("too_long", 0)
    if too_long_bullets > 0:
        suggestions.append(_s(
            "low", "content",
            f"Tighten {too_long_bullets} overlong bullets",
            f"{too_long_bullets} bullets exceed 260 characters. Tighten them for scannability.",
            "Recruiters skim; shorter, punchier bullets have higher read rates.",
        ))

    # De-dupe (an ats-warning-derived suggestion and a module-derived one
    # could theoretically overlap in title) and sort high → medium → low.
    seen_titles = set()
    deduped = []
    for s in suggestions:
        if s["title"] in seen_titles:
            continue
        seen_titles.add(s["title"])
        deduped.append(s)

    deduped.sort(key=lambda s: _PRIORITY_ORDER.get(s["priority"], 3))
    return deduped