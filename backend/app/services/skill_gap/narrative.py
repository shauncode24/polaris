# backend/app/services/skill_gap/narrative.py
"""Skill Gap narrative generation — diagnostic scope only.

build_narrative_context assembles the deterministic comparison facts into a
dict that the LLM prompt can reason over. It intentionally excludes
learning-plan, resume, and interview data: those concerns belong to other
modules (Career Planner, Resume, Interview). The LLM is only allowed to
synthesise what is already computed here.
"""
import logging

from app.core.llm import Prompt, llm_json
from app.prompts.skill_gap.narrative import INTERPRETATION_SYSTEM_PROMPT
from app.schemas.skill_gap.skill_gap import NarrativeAnalysis
from app.services.evidence.supporting import evidence_labels

logger = logging.getLogger(__name__)


class InterpretationError(Exception):
    """Raised when the narrative LLM call fails or returns something we
    can't validate. Callers fall back to fallback_narrative()."""


def build_narrative_context(
    *, role, company, have, partial, missing, priority_order,
    category_breakdown, overall_match,
    job_interview_focus_areas: list[str] | None = None,
) -> dict:
    """Assembles deterministic comparison facts for the LLM prompt.

    Deliberately omits: estimated_weeks_by_skill, learning_plan_curriculum,
    profile_context — those are Career Planner concerns.
    """
    return {
        "role": role,
        "company": company,
        "have": [
            {
                "skill": h.skill, "confidence": h.confidence,
                "evidence": evidence_labels(h.supporting), "explanation": h.explanation,
            }
            for h in have
        ],
        "partial": [
            {"skill": p.skill, "confidence": p.confidence, "reason": p.reason, "explanation": p.explanation}
            for p in partial
        ],
        "missing": [
            {"skill": m.skill, "reason": m.reason, "explanation": m.explanation}
            for m in missing
        ],
        "missing_priority_order": priority_order,
        "category_breakdown": category_breakdown,
        "overall_match_percentage": overall_match["percentage"],
        "overall_match_label": overall_match["label"],
        "job_interview_focus_areas": job_interview_focus_areas or [],
    }


async def generate_narrative_analysis(context: dict) -> NarrativeAnalysis:
    logger.debug("Requesting narrative interpretation from LLM...")

    def tidy(payload: dict) -> dict:
        # Normalise list fields in case the model returns a bare string, and
        # drop any extra keys it invented (career planning etc.).
        for key in ("role_focus", "strengths", "risks"):
            value = payload.get(key, [])
            payload[key] = [value] if isinstance(value, str) else value
        allowed = ("executive_summary", "role_focus", "strengths", "risks")
        return {key: payload[key] for key in allowed if key in payload}

    try:
        reply = await llm_json(
            Prompt(INTERPRETATION_SYSTEM_PROMPT, context), NarrativeAnalysis,
            label="skill_gap_narrative", expect=("executive_summary", "risks"), prepare=tidy,
            temperature=0.3, max_tokens=1500,
        )
    except Exception as e:
        raise InterpretationError(f"Narrative LLM call failed: {e}") from e
    return reply.value


def fallback_narrative(context: dict) -> NarrativeAnalysis:
    have_names = [h["skill"] for h in context["have"]]
    missing_names = context["missing_priority_order"]
    role_focus = context.get("job_interview_focus_areas") or ["Production backend engineering", "Scalable architectures"]

    summary = (
        f"This profile is a {context['overall_match_label'].lower()} "
        f"({context['overall_match_percentage']}%) for this role."
    )
    if have_names:
        summary += f" Strongest verified skills: {', '.join(have_names[:4])}."
    if missing_names:
        summary += f" Most significant gaps: {', '.join(missing_names[:4])}."

    return NarrativeAnalysis(
        executive_summary=summary,
        role_focus=role_focus[:5],
        strengths=[f"Verified evidence for {h['skill']}" for h in context["have"][:4]],
        risks=[f"No verified evidence for {m['skill']}" for m in context["missing"][:4]],
    )