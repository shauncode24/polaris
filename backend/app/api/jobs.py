# backend/app/api/jobs.py
from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from pydantic import BaseModel

from app.core.database import get_db
from app.models.facts import JobDescription, Project, Resume
from app.models.job_intelligence import GapAnalysisResultRow
from app.services.projects.linking import normalize_name
from app.schemas.interpretation import CategoryScore, OverallMatch, SkillGapAnalysisResponse
from app.schemas.skill_gap import JDPasteRequest
from app.services.job_intelligence.builder import JobIntelligenceExtractionError, build_job_intelligence
from app.services.target_profile.builder import build_target_profile
from app.services.skill_gap.comparison import analyze_skill_gap
from app.services.skill_gap.category_breakdown import (
    compute_category_breakdown,
    compute_overall_match,
    compute_peer_benchmarks,
)
from app.services.skill_gap.narrative import (
    InterpretationError,
    build_narrative_context,
    fallback_narrative,
    generate_narrative_analysis,
)
from app.services.resume.pdf_parser import extract_text_from_pdf
from app.api.deps import get_current_user
from app.models.facts import User
from app.services.identity.identity_refresh import trigger_identity_refresh

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _fetch_profile_context(db, user_id, max_projects: int = 6) -> list[dict]:
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


async def _get_latest_gap_result_row(db, job_intelligence_id) -> GapAnalysisResultRow | None:
    """The GapAnalysisResultRow this JD's SkillGapAnalysisResponse should
    actually be built from — its append-only, source-tagged lineage
    against both the JobIntelligenceProfile and CompanyIntelligenceProfile
    it was compared against, same pattern as LeetcodeEngineeringSnapshot
    / EngineeringIdentity elsewhere in this codebase. Most recent wins,
    since a re-analysis of the exact same job_intelligence_id (rare, but
    possible via re-running the comparison) should supersede an older one.
    """
    if job_intelligence_id is None:
        return None
    result = await db.execute(
        select(GapAnalysisResultRow)
        .where(GapAnalysisResultRow.job_intelligence_id == job_intelligence_id)
        .order_by(GapAnalysisResultRow.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _response_from_gap_result_row(row: GapAnalysisResultRow) -> SkillGapAnalysisResponse:
    return SkillGapAnalysisResponse(
        report=row.report_json,
        category_breakdown=[CategoryScore(**c) for c in row.category_breakdown_json.get("items", [])],
        overall_match=OverallMatch(**row.overall_match_json),
        analysis=row.narrative_json,
        analysis_degraded=row.analysis_degraded,
    )


async def _run_job_analysis(
    raw_text: str,
    company: str | None,
    role: str | None,
    user: User,
    db,
) -> SkillGapAnalysisResponse:
    """The one function in the codebase that knows BOTH the Job
    Intelligence pipeline and the Comparison Engine exist — everything
    downstream of this stays clean (design doc §5.5, revision's
    high-level architecture diagram).
    """
    print(f"[TRACING] Received JD analysis request, length={len(raw_text)}", flush=True)

    # JobIntelligenceExtractionError propagates to the route handlers
    # below, which translate it into an HTTP 502 — there is no
    # deterministic fallback for a failed extraction (see builder.py).
    job_intelligence, company_intelligence = await build_job_intelligence(db, user.id, raw_text, company, role)
    target_profile = build_target_profile(job_intelligence, company_intelligence)

    print(
        f"[TRACING] Job Intelligence extracted {len(job_intelligence.enriched_required_skills)} required, "
        f"{len(job_intelligence.enriched_implicit_skills)} implicit, "
        f"{len(job_intelligence.enriched_nice_to_have)} nice-to-have, "
        f"{len(job_intelligence.architecture_topics)} architecture topics "
        f"(extraction_quality={job_intelligence.extraction_quality.label}).",
        flush=True,
    )

    resolved_role = job_intelligence.role
    resolved_company = job_intelligence.company

    job_description = JobDescription(
        user_id=user.id,
        company=resolved_company,
        role=resolved_role,
        raw_text=raw_text,
        job_intelligence_id=UUID(job_intelligence.id),
        company_intelligence_id=UUID(company_intelligence.id) if company_intelligence.id else None,
        # Dual-written for backward compatibility during the transition —
        # career_planner/context_builder.py and resume/tailoring_llm.py
        # still read this field unchanged (design doc Phase 2/4).
        extracted_requirements={
            "raw_required": [s.raw for s in job_intelligence.enriched_required_skills],
            "raw_implicit": [s.raw for s in job_intelligence.enriched_implicit_skills],
            "raw_nice_to_have": [s.raw for s in job_intelligence.enriched_nice_to_have],
            "architecture_topics": job_intelligence.architecture_topics,
            "resolved_skills": list(job_intelligence.canonical_skills_map.keys()),
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(job_description)
    await db.flush()
    await db.commit()

    report = await analyze_skill_gap(db, user.id, target_profile.job_intelligence)
    print(
        f"[TRACING] Gap analysis complete: {len(report.have)} have, {len(report.partial)} partial, "
        f"{len(report.missing)} missing, {report.estimated_weeks} total estimated weeks.",
        flush=True,
    )

    category_breakdown = compute_category_breakdown(report.have, report.partial, report.missing)
    overall_match = compute_overall_match(
        target_profile.job_intelligence.canonical_skills_map, report.have, report.partial, report.missing,
    )
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
        job_interview_focus_areas=target_profile.job_intelligence.interview_focus_areas,
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

    # Dual-write: keep JobDescription.analysis_result populated (Phase 2/3
    # rollout safety — legacy pre-refactor rows with no job_intelligence_id
    # still need SOME read path) AND persist a proper GapAnalysisResult
    # row for lineage against both source profiles. GET /jobs and
    # GET /jobs/{id} now read GapAnalysisResultRow as the primary source
    # of truth (see below) and only fall back to this blob for legacy rows.
    job_description.analysis_result = response.model_dump(mode="json")
    await db.commit()

    gap_result_row = GapAnalysisResultRow(
        user_id=user.id,
        job_intelligence_id=UUID(job_intelligence.id),
        company_intelligence_id=UUID(company_intelligence.id) if company_intelligence.id else None,
        report_json=report.model_dump(mode="json"),
        category_breakdown_json={"items": category_breakdown},
        overall_match_json=overall_match,
        narrative_json=analysis.model_dump(mode="json"),
        analysis_degraded=degraded,
        created_at=datetime.now(timezone.utc),
    )
    db.add(gap_result_row)
    await db.commit()
    print(
        f"[TRACING] Skill gap analysis + narrative persisted "
        f"(JobDescription id={job_description.id}, GapAnalysisResult id={gap_result_row.id}).",
        flush=True,
    )

    await trigger_identity_refresh(db, user.id, "job description analysis")

    return response


@router.post("/analyze", response_model=SkillGapAnalysisResponse)
async def analyze_job_description(
    payload: JDPasteRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        return await _run_job_analysis(payload.raw_text, payload.company, payload.role, current_user, db)
    except JobIntelligenceExtractionError as e:
        raise HTTPException(status_code=502, detail=str(e))


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
    try:
        return await _run_job_analysis(raw_text, company, role, current_user, db)
    except JobIntelligenceExtractionError as e:
        raise HTTPException(status_code=502, detail=str(e))


class JobAnalysisSummary(BaseModel):
    id: str
    company: str | None = None
    role: str | None = None
    created_at: datetime
    overall_match_percentage: float | None = None
    overall_match_label: str | None = None


@router.get("", response_model=list[JobAnalysisSummary])
async def list_job_analyses(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(
        select(JobDescription)
        .where(JobDescription.user_id == current_user.id)
        .where(JobDescription.analysis_result.isnot(None))
        .order_by(JobDescription.created_at.desc())
    )
    rows = result.scalars().all()

    summaries = []
    for jd in rows:
        # Prefer the real GapAnalysisResultRow lineage; only fall back to
        # the legacy analysis_result blob for pre-refactor rows that have
        # no job_intelligence_id at all.
        gap_row = await _get_latest_gap_result_row(db, jd.job_intelligence_id)
        if gap_row is not None:
            overall = gap_row.overall_match_json or {}
        else:
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
    if jd is None:
        raise HTTPException(status_code=404, detail="Job analysis not found")

    # Primary read path: the real, lineage-carrying GapAnalysisResultRow,
    # tied to both source profiles rather than a flattened JSONB blob.
    gap_row = await _get_latest_gap_result_row(db, jd.job_intelligence_id)
    if gap_row is not None:
        return _response_from_gap_result_row(gap_row)

    # Legacy fallback — pre-refactor JobDescription rows with no
    # job_intelligence_id (and therefore no GapAnalysisResultRow) still
    # read from the dual-written blob.
    if jd.analysis_result is None:
        raise HTTPException(status_code=404, detail="Job analysis not found")
    return SkillGapAnalysisResponse.model_validate(jd.analysis_result)