# backend/app/services/skill_gap/narrative.py
"""Skill Gap narrative generation — diagnostic scope only.

build_narrative_context assembles the deterministic comparison facts into a
dict that the LLM prompt can reason over. It intentionally excludes
learning-plan, resume, and interview data: those concerns belong to other
modules (Career Planner, Resume, Interview). The LLM is only allowed to
synthesise what is already computed here.
"""
import json

from app.core.llm import chat_completion, MODEL
from app.prompts.skill_gap_narrative import INTERPRETATION_SYSTEM_PROMPT
from app.schemas.interpretation import NarrativeAnalysis


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
            {"skill": h.skill, "confidence": h.confidence, "evidence": h.evidence, "explanation": h.explanation}
            for h in have
        ],
        "partial": [
            {"skill": p.skill, "confidence": p.confidence, "reason": p.reason, "explanation": p.explanation}
            for p in partial
        ],
        "missing": [
            {"skill": m.skill, "reason": m.reason, "unmatched_explanation": m.unmatched_explanation}
            for m in missing
        ],
        "missing_priority_order": priority_order,
        "category_breakdown": category_breakdown,
        "overall_match_percentage": overall_match["percentage"],
        "overall_match_label": overall_match["label"],
        "job_interview_focus_areas": job_interview_focus_areas or [],
    }


async def generate_narrative_analysis(context: dict) -> NarrativeAnalysis:
    print("[TRACING] Requesting narrative interpretation from LLM...", flush=True)
    try:
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": INTERPRETATION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1500,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw narrative JSON:\n{content}", flush=True)
        parsed_dict = json.loads(content)

        # Normalise list fields in case LLM returns a bare string
        for list_key in ["role_focus", "strengths", "risks"]:
            if list_key in parsed_dict and isinstance(parsed_dict[list_key], str):
                parsed_dict[list_key] = [parsed_dict[list_key]]
            elif list_key not in parsed_dict:
                parsed_dict[list_key] = []

        # Drop any extra keys the LLM may have hallucinated (career planning etc.)
        allowed_keys = {"executive_summary", "role_focus", "strengths", "risks"}
        parsed_dict = {k: v for k, v in parsed_dict.items() if k in allowed_keys}

        parsed = NarrativeAnalysis.model_validate(parsed_dict)
    except Exception as e:
        raise InterpretationError(f"Narrative LLM call failed: {e}") from e

    return parsed


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