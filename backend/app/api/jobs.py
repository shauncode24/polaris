from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.models.facts import JobDescription, Project, Resume
from app.services.projects.linking import normalize_name
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
from app.services.jobs.skill_categories import (
    compute_category_breakdown,
    compute_overall_match,
    compute_peer_benchmarks,
)
from app.services.resume.pdf_parser import extract_text_from_pdf
from app.services.resume.skill_classifier import resolve_skills
from app.api.deps import get_current_user
from app.models.facts import User

router = APIRouter(prefix="/jobs", tags=["jobs"])

_CATEGORY_PRECEDENCE = ["required", "implicit", "nice_to_have"]


async def _fetch_profile_context(db, user_id, max_projects: int = 6) -> list[dict]:
    """Grounds resume_advice in real project data instead of letting the
    LLM guess at what the candidate has built.
    """
    result = await db.execute(
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
    )
    all_p = result.scalars().all()
    seen = set()
    projects = []
    for p in all_p:
        norm = normalize_name(p.name)
        if norm not in seen:
            seen.add(norm)
            projects.append({"name": p.name, "description": p.description, "stack": p.stack or []})
    return projects[:max_projects]


async def _run_job_analysis(
    raw_text: str,
    company: str | None,
    role: str | None,
    user: User,
    db,
) -> SkillGapAnalysisResponse:
    """Shared pipeline for both the text-paste and PDF-upload entry points.
    Everything from extraction through persistence lives here exactly once
    so the two endpoints can never drift out of sync with each other.
    """
    print(f"[TRACING] Received JD analysis request, length={len(raw_text)}", flush=True)

    extraction = await extract_jd_requirements(raw_text)
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

    resolved_role = role or extraction.role
    resolved_company = company or extraction.company

    job_description = JobDescription(
        user_id=user.id,
        company=resolved_company,
        role=resolved_role,
        raw_text=raw_text,
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
        db, user.id, canonical_skills, extraction.architecture_topics,
        role=resolved_role, company=resolved_company,
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
        role=resolved_role,
        company=resolved_company,
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


@router.post("/analyze", response_model=SkillGapAnalysisResponse)
async def analyze_job_description(
    payload: JDPasteRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    return await _run_job_analysis(payload.raw_text, payload.company, payload.role, current_user, db)


@router.post("/analyze-pdf", response_model=SkillGapAnalysisResponse)
async def analyze_job_description_pdf(
    file: UploadFile = File(...),
    company: str | None = Form(None),
    role: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    raw_bytes = await file.read()
    raw_text = extract_text_from_pdf(BytesIO(raw_bytes))
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in this PDF.")
    return await _run_job_analysis(raw_text, company, role, current_user, db)

class JobAnalysisSummary(BaseModel):
    id: str
    company: str | None = None
    role: str | None = None
    created_at: datetime
    overall_match_percentage: float | None = None
    overall_match_label: str | None = None


@router.get("", response_model=list[JobAnalysisSummary])
async def list_job_analyses(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    """Every past job analysis for this user, most recent first — only
    ones that actually finished analysis (analysis_result populated).
    Lightweight: pulls just the overall_match summary out of the stored
    JSON, not the full report, so the history list stays cheap to load.
    """
    result = await db.execute(
        select(JobDescription)
        .where(JobDescription.user_id == current_user.id)
        .where(JobDescription.analysis_result.isnot(None))
        .order_by(JobDescription.created_at.desc())
    )
    rows = result.scalars().all()

    summaries = []
    for jd in rows:
        overall = (jd.analysis_result or {}).get("overall_match", {})
        summaries.append(
            JobAnalysisSummary(
                id=str(jd.id),
                company=jd.company,
                role=jd.role,
                created_at=jd.created_at,
                overall_match_percentage=overall.get("percentage"),
                overall_match_label=overall.get("label"),
            )
        )
    return summaries


@router.get("/{job_id}", response_model=SkillGapAnalysisResponse)
async def get_job_analysis(
    job_id: UUID, current_user: User = Depends(get_current_user), db=Depends(get_db)
):
    result = await db.execute(
        select(JobDescription).where(
            JobDescription.id == job_id, JobDescription.user_id == current_user.id
        )
    )
    jd = result.scalar_one_or_none()
    if jd is None or jd.analysis_result is None:
        raise HTTPException(status_code=404, detail="Job analysis not found")
    return SkillGapAnalysisResponse.model_validate(jd.analysis_result)