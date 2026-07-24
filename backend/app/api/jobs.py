from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.models.facts import JobDescription
from app.schemas.skill_gap import JDPasteRequest, SkillGapReport
from app.services.jobs.gap_analysis import analyze_skill_gap
from app.services.jobs.jd_extraction import extract_jd_requirements
from app.services.resume.skill_classifier import resolve_skills
from app.services.user_helpers import get_or_create_default_user

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/analyze", response_model=SkillGapReport)
async def analyze_job_description(payload: JDPasteRequest, db=Depends(get_db)):
    print(f"[TRACING] Received JD paste request, length={len(payload.raw_text)}", flush=True)
    user = await get_or_create_default_user(db)

    extraction = await extract_jd_requirements(payload.raw_text)
    print(f"[TRACING] JD extraction found {len(extraction.required_skills)} required skills.", flush=True)

    resolved = await resolve_skills(set(extraction.required_skills), db)

    # Canonical, deduplicated, in the JD's own original order — used both
    # for persistence and as the tie-breaker in analyze_skill_gap().
    canonical_order: list[str] = []
    seen: set[str] = set()
    for raw in extraction.required_skills:
        canonical = resolved.get(raw)
        if canonical and canonical not in seen:
            canonical_order.append(canonical)
            seen.add(canonical)

    job_description = JobDescription(
        user_id=user.id,
        company=payload.company or extraction.company,
        role=payload.role or extraction.role,
        raw_text=payload.raw_text,
        extracted_requirements={
            "raw_skills": extraction.required_skills,
            "resolved_skills": canonical_order,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(job_description)
    await db.flush()
    await db.commit()

    report = await analyze_skill_gap(db, user.id, canonical_order)
    print(
        f"[TRACING] Gap analysis complete: {len(report.have)} have, "
        f"{len(report.missing)} missing, {report.estimated_weeks} weeks estimated.",
        flush=True,
    )
    return report