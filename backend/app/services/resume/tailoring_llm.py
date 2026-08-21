import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.facts import Experience, JobDescription, Project
from app.models.inference import ResumeTailoringReview, ProjectClaimAuditReview
from app.prompts.resume.resume_tailoring import TAILORING_SYSTEM_PROMPT
from app.schemas.resume.resume_tailoring import RankedItem, TailoringLLMOutput, TailoringReport
from app.services.evidence import get_all_skill_confidences
from app.services.resume.coherence_narrative import build_bullets_with_strength
from app.services.resume.skill_classifier import resolve_skills

logger = logging.getLogger(__name__)
from app.services.resume.tailoring_ranking import rank_items_for_jd
from app.services.resume.text_sanitize import sanitize_ai_text

MAX_BULLETS_IN_PROMPT = 40

# FIX (Important #5): same idea projects/comparison.py already applies to
# its goal-aware ranking — an unresolved claim-risk finding should reduce
# how strongly Tailoring recommends leading with a project.
from app.services.resume.claim_risk import CLAIM_RISK_MULTIPLIER, apply_claim_risk_penalty


async def _get_claim_risk_by_project_id(db: AsyncSession, project_ids: list) -> dict:
    """project_id -> "high"|"medium", for projects with an unresolved
    Claim Audit risk finding. Mirrors how the Projects module's
    goal-aware ranking already reads this same table.
    """
    if not project_ids:
        return {}
    result = await db.execute(
        select(ProjectClaimAuditReview).where(ProjectClaimAuditReview.project_id.in_(project_ids))
    )
    risk_by_id = {}
    for row in result.scalars().all():
        level = (row.report_json or {}).get("narrative", {}).get("risk_level")
        if level in ("high", "medium"):
            risk_by_id[row.project_id] = level
    return risk_by_id


class TailoringGenerationError(Exception):
    """Raised when the tailoring LLM call fails or returns something we
    can't validate. Same graceful-degradation pattern as
    PrioritizationError/InterpretationError elsewhere in this codebase.
    """


async def get_cached_tailoring_report(
    db: AsyncSession, resume_id, job_description_id
) -> TailoringReport | None:
    """Returns the last persisted tailoring report for this exact
    (resume, job_description) pair, or None if it's never been run.
    Tailoring is an LLM call — callers should read this back instead of
    calling generate_tailoring_report() again unless the resume or the
    target JD actually changed.
    """
    result = await db.execute(
        select(ResumeTailoringReview)
        .where(ResumeTailoringReview.resume_id == resume_id)
        .where(ResumeTailoringReview.job_description_id == job_description_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return TailoringReport.model_validate(row.report_json)


async def _persist_tailoring_report(
    db: AsyncSession, user_id, resume_id, job_description_id, report: TailoringReport
) -> None:
    payload = report.model_dump(mode="json")
    stmt = (
        pg_insert(ResumeTailoringReview)
        .values(
            user_id=user_id,
            resume_id=resume_id,
            job_description_id=job_description_id,
            report_json=payload,
            created_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            constraint="uq_tailoring_resume_jd",
            set_={"report_json": payload, "created_at": datetime.now(timezone.utc)},
        )
    )
    await db.execute(stmt)
    await db.commit()


async def generate_tailoring_report(db: AsyncSession, user_id, resume_id, job_description_id) -> TailoringReport:
    jd_result = await db.execute(
        select(JobDescription).where(JobDescription.id == job_description_id, JobDescription.user_id == user_id)
    )
    jd = jd_result.scalar_one_or_none()
    if jd is None or not jd.extracted_requirements:
        raise ValueError("Job description not found or not yet analyzed.")

    raw_required = set(jd.extracted_requirements.get("raw_required", []))
    raw_implicit = set(jd.extracted_requirements.get("raw_implicit", []))
    raw_nice = set(jd.extracted_requirements.get("raw_nice_to_have", []))

    resolved_required = await resolve_skills(raw_required, db) if raw_required else {}
    resolved_implicit = await resolve_skills(raw_implicit, db) if raw_implicit else {}
    resolved_nice = await resolve_skills(raw_nice, db) if raw_nice else {}

    canonical_skills: dict[str, str] = {}
    for raw, canonical in resolved_required.items():
        if canonical:
            canonical_skills.setdefault(canonical, "required")
    for raw, canonical in resolved_implicit.items():
        if canonical:
            canonical_skills.setdefault(canonical, "implicit")
    for raw, canonical in resolved_nice.items():
        if canonical:
            canonical_skills.setdefault(canonical, "nice_to_have")

    exp_result = await db.execute(
        select(Experience).where(Experience.user_id == user_id, Experience.resume_id == resume_id)
    )
    experiences = list(exp_result.scalars().all())
    proj_result = await db.execute(
        select(Project).where(Project.user_id == user_id, Project.resume_id == resume_id)
    )
    projects = list(proj_result.scalars().all())

    raw_stack: set[str] = set()
    for e in experiences:
        raw_stack.update(e.stack or [])
    for p in projects:
        raw_stack.update(p.stack or [])
    resolved_stack = await resolve_skills(raw_stack, db) if raw_stack else {}

    items = []
    for e in experiences:
        canonicals = [resolved_stack.get(s) for s in (e.stack or []) if resolved_stack.get(s)]
        items.append({
            "id": str(e.id), "type": "experience",
            "label": f"{e.role} at {e.company}", "canonical_stack": canonicals,
        })
    for p in projects:
        canonicals = [resolved_stack.get(s) for s in (p.stack or []) if resolved_stack.get(s)]
        items.append({"id": str(p.id), "type": "project", "label": p.name, "canonical_stack": canonicals})

    ranked = rank_items_for_jd(items, canonical_skills)

    # FIX (Important #5): apply the same claim-risk penalty Projects'
    # goal-aware ranking already applies, so Tailoring never confidently
    # recommends leading with a project the Claim Audit has already
    # flagged as unsupported.
    claim_risk_by_id = await _get_claim_risk_by_project_id(db, [p.id for p in projects])
    for r in ranked:
        if r["type"] != "project":
            continue
        project_uuid = next((p.id for p in projects if str(p.id) == r["id"]), None)
        risk = claim_risk_by_id.get(project_uuid)
        if risk:
            r["relevance_score"] = round(apply_claim_risk_penalty(r["relevance_score"], risk), 2)
            r["claim_risk"] = risk
    ranked.sort(key=lambda r: r["relevance_score"], reverse=True)

    # FIX (cross-user evidence leak): user_id is now required by
    # get_all_skill_confidences.
    skill_confidence = await get_all_skill_confidences(db, user_id)
    bullets = await build_bullets_with_strength(db, user_id, resume_id, skill_confidence)
    bullets_sorted = sorted(bullets, key=lambda b: b["strength"]["score"], reverse=True)
    bullets_for_prompt = [
        {
            "bullet_id": b["bullet_id"], "source_label": b["source_label"], "text": b["text"],
            "strength_score": b["strength"]["score"],
            "matched_jd_skills": sorted({c for c in b["canonical_stack"] if c in canonical_skills}),
        }
        for b in bullets_sorted[:MAX_BULLETS_IN_PROMPT]
    ]

    context = {
        "role": jd.role, "company": jd.company,
        "required_skills": sorted(raw_required), "implicit_skills": sorted(raw_implicit),
        "nice_to_have": sorted(raw_nice),
        "ranked_items": ranked, "bullets": bullets_for_prompt,
        "claim_risk_flags": [
            {"project_id": str(pid), "risk_level": level}
            for pid, level in claim_risk_by_id.items()
        ],
    }

    degraded = False
    try:
        logger.debug("Requesting resume tailoring recommendations from LLM...")
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": TAILORING_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        logger.debug("Raw tailoring JSON:\n%s", content)
        llm_output = TailoringLLMOutput.model_validate(json.loads(content))
    except Exception as e:
        logger.warning("Tailoring generation degraded, using fallback: %s", e)
        llm_output = TailoringLLMOutput(
            lead_items=[r["id"] for r in ranked[:2]],
            cut_bullets=[b["bullet_id"] for b in bullets_for_prompt if b["strength_score"] < 40][:3],
            emphasize_bullets=[b["bullet_id"] for b in bullets_for_prompt if b["matched_jd_skills"]][:3],
            rationale="Narrative tailoring is temporarily unavailable — this is a deterministic fallback based on relevance ranking alone.",
        )
        degraded = True

    real_item_ids = {r["id"] for r in ranked}
    real_bullet_ids = {b["bullet_id"] for b in bullets_for_prompt}
    llm_output.lead_items = [i for i in llm_output.lead_items if i in real_item_ids]
    llm_output.cut_bullets = [b for b in llm_output.cut_bullets if b in real_bullet_ids]
    llm_output.emphasize_bullets = [b for b in llm_output.emphasize_bullets if b in real_bullet_ids]
    llm_output.rationale = sanitize_ai_text(llm_output.rationale)

    report = TailoringReport(
        role=jd.role, company=jd.company,
        ranked_items=[RankedItem(**r) for r in ranked],
        llm=llm_output, analysis_degraded=degraded,
    )

    await _persist_tailoring_report(db, user_id, resume_id, job_description_id, report)

    return report