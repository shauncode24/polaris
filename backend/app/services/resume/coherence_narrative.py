"""Orchestrates the narrative-coherence report: builds real bullets with
deterministic strength scores, computes deterministic coherence facts and
dilution, then asks the LLM to interpret those facts. The LLM never sees
raw resume text and never decides a fact — same boundary jobs/interpretation.py
and career_planner enforce elsewhere in this codebase.

Results are cached in `resume_coherence_reviews`, UPSERTED by
(resume_id, target_role) — recomputing narrative coherence costs an LLM
call, so once a report exists for a given resume + target role, callers
should read it back via get_cached_coherence_report() instead of calling
generate_coherence_report() again, unless the resume or the target role
actually changed.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.facts import Experience, Project
from app.models.inference import ResumeCoherenceReview
from app.prompts.resume_coherence import COHERENCE_SYSTEM_PROMPT
from app.schemas.resume_coherence import CoherenceFacts, CoherenceLLMOutput, CoherenceReport
from app.services.evidence import get_all_skill_confidences
from app.services.resume.analysis.bullet_strength import compute_bullet_strength
from app.services.resume.analysis.coherence import compute_narrative_facts
from app.services.resume.analysis.dilution import detect_dilution
from app.services.resume.skill_classifier import resolve_skills
from app.services.resume.text_sanitize import sanitize_ai_text
from app.services.resume.bullet_analysis import build_bullet_units


class CoherenceGenerationError(Exception):
    """Raised when the coherence narrative LLM call fails or returns
    something unvalidatable. Callers fall back to a deterministic
    template — same graceful-degradation pattern as InterpretationError.
    """


def _normalize_target_role(target_role: str | None) -> str:
    return (target_role or "").strip()


async def get_cached_coherence_report(
    db: AsyncSession, resume_id, target_role: str | None
) -> CoherenceReport | None:
    """Returns the last persisted coherence report for this exact
    (resume, target_role) pair, or None if it's never been run. The API
    layer checks this before calling generate_coherence_report(), so
    re-opening the Resume page doesn't trigger a fresh LLM call.
    """
    normalized_role = _normalize_target_role(target_role)
    result = await db.execute(
        select(ResumeCoherenceReview)
        .where(ResumeCoherenceReview.resume_id == resume_id)
        .where(ResumeCoherenceReview.target_role == normalized_role)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return CoherenceReport.model_validate(row.report_json)


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

    raw_units = build_bullet_units(experiences, projects)
    canonicals_by_source: dict[str, list[str]] = {}
    for e in experiences:
        canonicals_by_source[f"exp_{e.id}"] = [resolved.get(s) for s in (e.stack or []) if resolved.get(s)]
    for p in projects:
        canonicals_by_source[f"proj_{p.id}"] = [resolved.get(s) for s in (p.stack or []) if resolved.get(s)]

    bullets: list[dict] = []
    for unit in raw_units:
        prefix = "exp" if unit["source_type"] == "experience" else "proj"
        key = f"{prefix}_{unit['source_id']}"
        canonicals = canonicals_by_source.get(key, [])
        strength = compute_bullet_strength(unit["text"], unit["context_stack"], skill_confidence, canonicals)
        bullets.append({**unit, "canonical_stack": canonicals, "strength": strength})

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


def _sanitize_narrative(narrative: CoherenceLLMOutput) -> CoherenceLLMOutput:
    """Defense-in-depth: even though the prompt now forbids bullet_ids
    outside recommended_cuts, strip any that leak through into prose
    fields before this ever reaches the user.
    """
    narrative.argued_role = sanitize_ai_text(narrative.argued_role)
    narrative.positioning_statement = sanitize_ai_text(narrative.positioning_statement)
    narrative.strengths_for_this_story = [sanitize_ai_text(s) for s in narrative.strengths_for_this_story]
    narrative.weakens_the_story = [sanitize_ai_text(s) for s in narrative.weakens_the_story]
    narrative.recommendation = sanitize_ai_text(narrative.recommendation)
    return narrative


async def _persist_coherence_report(
    db: AsyncSession, user_id, resume_id, target_role: str | None, report: CoherenceReport
) -> None:
    normalized_role = _normalize_target_role(target_role)
    payload = report.model_dump(mode="json")
    stmt = (
        pg_insert(ResumeCoherenceReview)
        .values(
            user_id=user_id,
            resume_id=resume_id,
            target_role=normalized_role,
            report_json=payload,
            created_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            constraint="uq_coherence_resume_role",
            set_={"report_json": payload, "created_at": datetime.now(timezone.utc)},
        )
    )
    await db.execute(stmt)
    await db.commit()


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
    narrative = _sanitize_narrative(narrative)

    report = CoherenceReport(facts=facts, dilution=dilution, narrative=narrative, analysis_degraded=degraded)

    await _persist_coherence_report(db, user_id, resume_id, target_role, report)

    return report