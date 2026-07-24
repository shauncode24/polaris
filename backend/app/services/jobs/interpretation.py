import json

from app.core.llm import client, MODEL
from app.prompts.jd_interpretation import INTERPRETATION_SYSTEM_PROMPT
from app.schemas.interpretation import LearningPlanItem, NarrativeAnalysis


class InterpretationError(Exception):
    """Raised when the narrative LLM call fails or returns something we
    can't validate. Callers fall back to fallback_narrative() instead of
    crashing the whole report — same pattern as PrioritizationError."""


def build_narrative_context(
    *, role, company, have, partial, missing, priority_order,
    estimated_weeks_by_skill, category_breakdown, overall_match, profile_context,
) -> dict:
    return {
        "role": role,
        "company": company,
        "have": [{"skill": h.skill, "confidence": h.confidence, "evidence": h.evidence} for h in have],
        "partial": [{"skill": p.skill, "confidence": p.confidence, "reason": p.reason} for p in partial],
        "missing": [{"skill": m.skill, "reason": m.reason} for m in missing],
        "missing_priority_order": priority_order,
        "estimated_weeks_by_skill": estimated_weeks_by_skill,
        "category_breakdown": category_breakdown,
        "overall_match_percentage": overall_match["percentage"],
        "overall_match_label": overall_match["label"],
        "profile_context": profile_context,
    }


async def generate_narrative_analysis(context: dict) -> NarrativeAnalysis:
    print("[TRACING] Requesting narrative interpretation from LLM...", flush=True)
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": INTERPRETATION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context)},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw narrative JSON:\n{content}", flush=True)
        parsed = NarrativeAnalysis.model_validate(json.loads(content))
    except Exception as e:
        raise InterpretationError(f"Narrative LLM call failed: {e}") from e

    # Don't trust the model's learning_plan blindly — enforce it matches
    # the deterministic facts it was given, same "never trust the LLM's
    # list blindly" rule gap_analysis.py already applies to priority_order.
    valid_skills = set(context["missing_priority_order"])
    parsed.learning_plan = [item for item in parsed.learning_plan if item.skill in valid_skills]
    if not parsed.learning_plan and context["missing_priority_order"]:
        parsed.learning_plan = [
            LearningPlanItem(
                skill=s,
                weeks=context["estimated_weeks_by_skill"].get(s, 1),
                rationale="Flagged as a priority gap in the skill-gap analysis.",
            )
            for s in context["missing_priority_order"]
        ]

    return parsed


def fallback_narrative(context: dict) -> NarrativeAnalysis:
    """Deterministic, template-built narrative for when the LLM call
    fails. Weaker prose than a real explanation, but every field is
    grounded in the same facts the LLM would have used — the UI never
    renders an empty analysis panel.
    """
    have_names = [h["skill"] for h in context["have"]]
    missing_names = context["missing_priority_order"]

    summary = (
        f"This profile is a {context['overall_match_label'].lower()} "
        f"({context['overall_match_percentage']}%) for this role."
    )
    if have_names:
        summary += f" Strongest verified skills: {', '.join(have_names[:4])}."
    if missing_names:
        summary += f" Biggest gaps: {', '.join(missing_names[:4])}."

    learning_plan = [
        LearningPlanItem(
            skill=s,
            weeks=context["estimated_weeks_by_skill"].get(s, 1),
            rationale="Flagged as a priority gap in the skill-gap analysis.",
        )
        for s in missing_names
    ]

    return NarrativeAnalysis(
        executive_summary=summary,
        strengths=[f"Verified evidence for {h['skill']}" for h in context["have"][:4]],
        risks=[f"No verified evidence for {m['skill']}" for m in context["missing"][:4]],
        learning_plan=learning_plan,
        resume_advice=[],
        interview_focus=missing_names[:5],
        confidence_narrative="; ".join(
            f"{c['category']}: {c['label']}" for c in context["category_breakdown"]
        ),
    )