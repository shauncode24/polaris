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

# Precedence when the same canonical skill shows up in more than one
# category (e.g. named directly AND implied by a responsibility) — the
# strongest/most-committal category wins.
_CATEGORY_PRECEDENCE = ["required", "implicit", "nice_to_have"]


@router.post("/analyze", response_model=SkillGapReport)
async def analyze_job_description(payload: JDPasteRequest, db=Depends(get_db)):
    print(f"[TRACING] Received JD paste request, length={len(payload.raw_text)}", flush=True)
    user = await get_or_create_default_user(db)

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

    job_description = JobDescription(
        user_id=user.id,
        company=payload.company or extraction.company,
        role=payload.role or extraction.role,
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
        db,
        user.id,
        canonical_skills,
        extraction.architecture_topics,
        role=payload.role or extraction.role,
        company=payload.company or extraction.company,
    )
    print(
        f"[TRACING] Gap analysis complete: {len(report.have)} have, {len(report.partial)} partial, "
        f"{len(report.missing)} missing, {report.estimated_weeks} total estimated weeks.",
        flush=True,
    )
    return report