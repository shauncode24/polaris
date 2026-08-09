# backend/app/services/skill_gap/narrative.py
"""Moved from jobs/interpretation.py. build_narrative_context now takes
job_interview_focus_areas (a real Job-Intelligence fact) so the LLM's
role_focus/interview_focus fields stay consistent across every user
targeting the same JD, per §5.4.
"""
import json

from app.core.llm import chat_completion, MODEL
from app.prompts.skill_gap_narrative import INTERPRETATION_SYSTEM_PROMPT
from app.schemas.interpretation import LearningPlanItem, NarrativeAnalysis
from app.services.taxonomy.skill_taxonomy import get_curriculum_phase


class InterpretationError(Exception):
    """Raised when the narrative LLM call fails or returns something we
    can't validate. Callers fall back to fallback_narrative()."""


def build_narrative_context(
    *, role, company, have, partial, missing, priority_order,
    estimated_weeks_by_skill, category_breakdown, overall_match, profile_context,
    job_interview_focus_areas: list[str] | None = None,
) -> dict:
    learning_plan_curriculum = [
        {"skill": s, "weeks": estimated_weeks_by_skill.get(s, 1), "phase": get_curriculum_phase(s)}
        for s in priority_order
    ]

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
        "learning_plan_curriculum": learning_plan_curriculum,
        "estimated_weeks_by_skill": estimated_weeks_by_skill,
        "category_breakdown": category_breakdown,
        "overall_match_percentage": overall_match["percentage"],
        "overall_match_label": overall_match["label"],
        "profile_context": profile_context,
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
            temperature=0.4,
            max_tokens=3000,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw narrative JSON:\n{content}", flush=True)
        parsed_dict = json.loads(content)
        for list_key in ["role_focus", "strengths", "risks", "resume_advice", "interview_focus", "next_steps"]:
            if list_key in parsed_dict and isinstance(parsed_dict[list_key], str):
                parsed_dict[list_key] = [parsed_dict[list_key]]
            elif list_key not in parsed_dict:
                parsed_dict[list_key] = []

        if "learning_plan" in parsed_dict and isinstance(parsed_dict["learning_plan"], list):
            for item in parsed_dict["learning_plan"]:
                if isinstance(item, dict):
                    if "phase" not in item or not item["phase"]:
                        item["phase"] = get_curriculum_phase(item.get("skill", ""))
                    if "rationale" not in item or not item["rationale"]:
                        item["rationale"] = f"Flagged as a priority gap in the {item.get('phase', 'General')} phase."
        parsed = NarrativeAnalysis.model_validate(parsed_dict)
    except Exception as e:
        raise InterpretationError(f"Narrative LLM call failed: {e}") from e

    valid_skills = set(context["missing_priority_order"])
    parsed.learning_plan = [item for item in parsed.learning_plan if item.skill in valid_skills]
    for item in parsed.learning_plan:
        item.phase = get_curriculum_phase(item.skill)
        item.weeks = context["estimated_weeks_by_skill"].get(item.skill, item.weeks)

    if not parsed.learning_plan and context["missing_priority_order"]:
        parsed.learning_plan = [
            LearningPlanItem(
                skill=s, weeks=context["estimated_weeks_by_skill"].get(s, 1),
                rationale="Flagged as a priority gap in the skill-gap analysis.", phase=get_curriculum_phase(s),
            )
            for s in context["missing_priority_order"]
        ]

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
        summary += f" Biggest gaps: {', '.join(missing_names[:4])}."

    learning_plan = [
        LearningPlanItem(
            skill=s, weeks=context["estimated_weeks_by_skill"].get(s, 1),
            rationale="Flagged as a priority gap in the skill-gap analysis.", phase=get_curriculum_phase(s),
        )
        for s in missing_names
    ]

    return NarrativeAnalysis(
        executive_summary=summary,
        role_focus=role_focus[:5],
        strengths=[f"Verified evidence for {h['skill']}" for h in context["have"][:4]],
        risks=[f"No verified evidence for {m['skill']}" for m in context["missing"][:4]],
        learning_plan=learning_plan,
        resume_advice=[],
        interview_focus=(context.get("job_interview_focus_areas") or missing_names)[:5],
        hiring_perspective="; ".join(
            f"{c['category']}: {c['label']}" for c in context["category_breakdown"]
        ),
        career_strategy="Prioritize learning required missing technologies first.",
        next_steps=[
            "Build a small project demonstrating your top missing required skill.",
            "Add the new project and deployment details to your resume.",
            "Prepare for interview questions on your weakest evidenced area.",
        ],
    )