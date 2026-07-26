from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.database import get_db
from app.models.facts import JobDescription, Project
from app.schemas.interpretation import CategoryScore, OverallMatch, SkillGapAnalysisResponse
from app.schemas.skill_gap import JDPasteRequest
from app.services.jobs.gap_analysis import analyze_skill_gap
from app.services.jobs.interpretation import (
    InterpretationError,
    build_narrative_context,
    fallback_narrative,
    generate_narrative_analysis,
)
from app.services.jobs.jd_extraction import extract_jd_requirements
from app.services.jobs.skill_categories import compute_category_breakdown, compute_overall_match, compute_peer_benchmarks
from app.services.resume.skill_classifier import resolve_skills
from app.api.deps import get_current_user
from app.models.facts import User

router = APIRouter(prefix="/jobs", tags=["jobs"])

_CATEGORY_PRECEDENCE = ["required", "implicit", "nice_to_have"]


async def _fetch_profile_context(db, user_id, max_projects: int = 6) -> list[dict]:
    """Grounds resume_advice in real project data instead of letting the
    LLM guess at what the candidate has built.
    """
    result = await db.execute(select(Project).where(Project.user_id == user_id).limit(max_projects))
    return [
        {"name": p.name, "description": p.description, "stack": p.stack or []}
        for p in result.scalars().all()
    ]


@router.post("/analyze", response_model=SkillGapAnalysisResponse)
async def analyze_job_description(payload: JDPasteRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    print(f"[TRACING] Received JD paste request, length={len(payload.raw_text)}", flush=True)
    user = current_user

    extraction = await extract_jd_requirements(payload.raw_text)
    print(
        f"[TRACING] JD extraction found {len(extraction.required_skills)} required, "
        f"{len(extraction.implicit_skills)} implicit, {len(extraction.nice_to_have)} nice-to-have, "
        f"{len(extraction.architecture_topics)} architecture topics.",
        flush=True,
    )

    raw_by_category = {
        "required": extraction.required_skills,
        "implicit": extraction.implicit_skills,
        "nice_to_have": extraction.nice_to_have,
    }
    all_raw_strings = {s for skills in raw_by_category.values() for s in skills}
    resolved = await resolve_skills(all_raw_strings, db)

    canonical_skills: dict[str, str] = {}
    canonical_order: list[str] = []
    for category in _CATEGORY_PRECEDENCE:
        for raw in raw_by_category[category]:
            canonical = resolved.get(raw)
            if canonical is None:
                continue
            if canonical not in canonical_skills:
                canonical_skills[canonical] = category
                canonical_order.append(canonical)

    role = payload.role or extraction.role
    company = payload.company or extraction.company

    job_description = JobDescription(
        user_id=user.id,
        company=company,
        role=role,
        raw_text=payload.raw_text,
        extracted_requirements={
            "raw_required": extraction.required_skills,
            "raw_implicit": extraction.implicit_skills,
            "raw_nice_to_have": extraction.nice_to_have,
            "architecture_topics": extraction.architecture_topics,
            "resolved_skills": canonical_order,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(job_description)
    await db.flush()
    await db.commit()

    report = await analyze_skill_gap(
        db, user.id, canonical_skills, extraction.architecture_topics, role=role, company=company,
    )
    print(
        f"[TRACING] Gap analysis complete: {len(report.have)} have, {len(report.partial)} partial, "
        f"{len(report.missing)} missing, {report.estimated_weeks} total estimated weeks.",
        flush=True,
    )

    category_breakdown = compute_category_breakdown(report.have, report.partial, report.missing)
    overall_match = compute_overall_match(canonical_skills, report.have, report.partial, report.missing)
    profile_context = await _fetch_profile_context(db, user.id)

    context = build_narrative_context(
        role=role,
        company=company,
        have=report.have,
        partial=report.partial,
        missing=report.missing,
        priority_order=report.priority_order,
        estimated_weeks_by_skill={m.skill: m.estimated_weeks for m in report.missing},
        category_breakdown=category_breakdown,
        overall_match=overall_match,
        profile_context=profile_context,
    )

    degraded = False
    try:
        analysis = await generate_narrative_analysis(context)
    except InterpretationError as e:
        print(f"[TRACING] Narrative generation degraded, using fallback: {e}", flush=True)
        analysis = fallback_narrative(context)
        degraded = True

    response = SkillGapAnalysisResponse(
        report=report,
        category_breakdown=[CategoryScore(**c) for c in category_breakdown],
        overall_match=OverallMatch(**overall_match),
        analysis=analysis,
        analysis_degraded=degraded,
    )

    job_description.analysis_result = response.model_dump(mode="json")
    await db.commit()
    print("[TRACING] Skill gap analysis + narrative persisted to job_descriptions.", flush=True)

    return response