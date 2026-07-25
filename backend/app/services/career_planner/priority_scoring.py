"""Lightweight, advisory skill-priority signal for Career Planner.

Deliberately NOT a gatekeeper: this does not decide what the LLM is
allowed to schedule, and nothing downstream rejects LLM output for
disagreeing with it. It's the same role confidence scores already play
elsewhere in this codebase (Skill Gap Analyzer, Resume Reviewer) — a
computed fact handed to the LLM to reason over, not a rule it must obey.
"""
from app.services.career_planner.goal_domains import goal_relevance_score

STRONG_CONFIDENCE_THRESHOLD = 0.75


def _has_project_evidence(evidence_details: list[str]) -> bool:
    return any(d.startswith("Project:") for d in evidence_details)


def build_skill_signals(
    skills_by_confidence: list[dict],   # [{"skill", "confidence", "evidence"}, ...]
    goal_title: str,
    jd_missing_skills: set[str],
    ats_missing_keywords: set[str],
    previous_skill_confidence: dict[str, float],
) -> list[dict]:
    """Returns one entry per skill the user has ANY evidence for, plus
    any JD-missing skill with zero evidence at all. Sorted lowest-
    confidence-first as a soft suggestion — the LLM is told explicitly
    this is a starting point, not an instruction list.

    Every skill also gets 'is_strong' (bool) as a plain fact, not a
    directive — the prompt asks the LLM to generally avoid spending a
    full day on strong skills, but doesn't forbid it outright (e.g. a
    strong skill might still be worth ONE day of "harden it further"
    work if genuinely nothing else fits the goal).
    """
    signals: list[dict] = []
    known = set()

    for entry in skills_by_confidence:
        skill = entry["skill"]
        confidence = entry["confidence"]
        known.add(skill)

        reasons = []
        if confidence < STRONG_CONFIDENCE_THRESHOLD:
            reasons.append(f"confidence {confidence:.2f} — limited evidence")
        if skill in jd_missing_skills:
            reasons.append("flagged missing in your most recent Skill Gap Analysis")
        if skill in ats_missing_keywords:
            reasons.append("flagged as a missing ATS keyword in your Resume Review")
        if goal_relevance_score(skill, goal_title) > 0:
            reasons.append(f"relevant to your goal: '{goal_title}'")
        prev = previous_skill_confidence.get(skill)
        if prev is not None and confidence <= prev:
            reasons.append("no confidence improvement since your last snapshot")
        if not _has_project_evidence(entry["evidence"]):
            reasons.append("no project currently demonstrates it")

        signals.append({
            "skill": skill,
            "confidence": confidence,
            "is_strong": confidence >= STRONG_CONFIDENCE_THRESHOLD,
            "reasons": reasons,
        })

    # Skills flagged missing (JD or resume ATS) with literally zero
    # profile evidence won't be in skills_by_confidence at all.
    for skill in (jd_missing_skills | ats_missing_keywords) - known:
        signals.append({
            "skill": skill,
            "confidence": 0.0,
            "is_strong": False,
            "reasons": [
                "zero verified evidence in your profile",
                "flagged missing in a recent Skill Gap Analysis or Resume Review",
            ],
        })

    signals.sort(key=lambda s: s["confidence"])
    return signals