"""Orchestrates the narrative-coherence report: builds real bullets with
deterministic strength scores, computes deterministic coherence facts and
dilution, then asks the LLM to interpret those facts. The LLM never sees
raw resume text and never decides a fact — same boundary jobs/interpretation.py
and career_planner enforce elsewhere in this codebase.
"""
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.facts import Experience, Project
from app.prompts.resume_coherence import COHERENCE_SYSTEM_PROMPT
from app.schemas.resume_coherence import CoherenceFacts, CoherenceLLMOutput, CoherenceReport
from app.services.evidence import get_all_skill_confidences
from app.services.resume.analysis.bullet_strength import compute_bullet_strength
from app.services.resume.analysis.coherence import compute_narrative_facts
from app.services.resume.analysis.dilution import detect_dilution
from app.services.resume.skill_classifier import resolve_skills


class CoherenceGenerationError(Exception):
    """Raised when the coherence narrative LLM call fails or returns
    something unvalidatable. Callers fall back to a deterministic
    template — same graceful-degradation pattern as InterpretationError.
    """


async def build_bullets_with_strength(
    db: AsyncSession, user_id, resume_id, skill_confidence: dict[str, float]
) -> list[dict]:
    """Shared by coherence and tailoring — the single real bullet list
    with strength scores and resolved canonical stacks, built once so
    both features describe the same bullets the same way.
    """
    exp_result = await db.execute(
        select(Experience).where(Experience.user_id == user_id, Experience.resume_id == resume_id)
    )
    experiences = list(exp_result.scalars().all())

    proj_result = await db.execute(
        select(Project).where(Project.user_id == user_id, Project.resume_id == resume_id)
    )
    projects = list(proj_result.scalars().all())

    raw_stack_strings: set[str] = set()
    for e in experiences:
        raw_stack_strings.update(e.stack or [])
    for p in projects:
        raw_stack_strings.update(p.stack or [])
    resolved = await resolve_skills(raw_stack_strings, db) if raw_stack_strings else {}

    bullets: list[dict] = []
    for exp in experiences:
        label = f"{exp.role} at {exp.company}"
        canonicals = [resolved.get(s) for s in (exp.stack or []) if resolved.get(s)]
        for i, bullet in enumerate(exp.bullets or []):
            if not bullet.strip():
                continue
            strength = compute_bullet_strength(bullet, exp.stack or [], skill_confidence, canonicals)
            bullets.append({
                "bullet_id": f"exp_{exp.id}_{i}", "source_type": "experience",
                "source_label": label, "text": bullet,
                "context_stack": exp.stack or [], "canonical_stack": canonicals,
                "strength": strength,
            })

    for proj in projects:
        canonicals = [resolved.get(s) for s in (proj.stack or []) if resolved.get(s)]
        lines = [l.strip("-•* \t") for l in (proj.description or "").split("\n") if l.strip()]
        for i, line in enumerate(lines):
            strength = compute_bullet_strength(line, proj.stack or [], skill_confidence, canonicals)
            bullets.append({
                "bullet_id": f"proj_{proj.id}_{i}", "source_type": "project",
                "source_label": proj.name, "text": line,
                "context_stack": proj.stack or [], "canonical_stack": canonicals,
                "strength": strength,
            })

    return bullets


def _fallback_narrative(facts: CoherenceFacts, dilution: dict) -> CoherenceLLMOutput:
    argued = facts.dominant_category or "an unclear specialization"
    return CoherenceLLMOutput(
        argued_role=argued,
        positioning_statement=(
            f"Based on verified skill signal, this resume currently argues most strongly for "
            f"{argued}. Narrative analysis is temporarily unavailable — this is a deterministic summary."
        ),
        strengths_for_this_story=[],
        weakens_the_story=[b["source_label"] for b in facts.off_narrative_bullets[:4]],
        recommended_cuts=[b["bullet_id"] for b in dilution.get("excess_bullets", [])[:3]],
        recommendation="Review the flagged off-narrative and low-strength bullets manually.",
    )


async def generate_coherence_report(
    db: AsyncSession, user_id, resume_id, target_role: str | None
) -> CoherenceReport:
    skill_confidence = await get_all_skill_confidences(db)
    bullets = await build_bullets_with_strength(db, user_id, resume_id, skill_confidence)

    facts_dict = compute_narrative_facts(skill_confidence, bullets, target_role)
    facts = CoherenceFacts(**facts_dict)
    dilution = detect_dilution(bullets)

    degraded = False
    try:
        print("[TRACING] Requesting resume coherence narrative from LLM...", flush=True)
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": COHERENCE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"facts": facts.model_dump(), "dilution": dilution})},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw coherence narrative JSON:\n{content}", flush=True)
        narrative = CoherenceLLMOutput.model_validate(json.loads(content))
    except Exception as e:
        print(f"[TRACING] Coherence narrative degraded, using fallback: {e}", flush=True)
        narrative = _fallback_narrative(facts, dilution)
        degraded = True

    # Never trust recommended_cuts blindly — must be real bullet_ids we
    # actually generated (same rule gap_analysis.py applies to priority_order).
    real_ids = {b["bullet_id"] for b in bullets}
    narrative.recommended_cuts = [c for c in narrative.recommended_cuts if c in real_ids]

    return CoherenceReport(facts=facts, dilution=dilution, narrative=narrative, analysis_degraded=degraded)