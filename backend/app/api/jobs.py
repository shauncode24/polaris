# backend/app/api/jobs.py
from datetime import datetime, timezone
from io import BytesIO
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from pydantic import BaseModel

from app.core.database import get_db
from app.core.settings import settings
from app.models.facts import JobDescription, Project, Resume
from app.models.job_intelligence import GapAnalysisResultRow
from app.services.projects.linking import normalize_name
from app.schemas.skill_gap.interpretation import CategoryScore, NarrativeAnalysis, OverallMatch, SkillGapAnalysisResponse
from app.schemas.skill_gap.skill_gap import JDPasteRequest
from app.schemas.skill_gap.skill_gap_page import SkillGapForJobResponse
from app.services.job_intelligence.builder import (
    JobIntelligenceExtractionError,
    build_job_intelligence,
    get_job_intelligence,
)
from app.services.company_intelligence.reader import get_company_intelligence_by_source_hash
from app.services.target_profile.builder import build_target_profile
from app.services.skill_gap.comparison import analyze_skill_gap
from app.services.skill_gap.category_breakdown import (
    compute_category_breakdown,
    compute_overall_match,
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
logger = logging.getLogger(__name__)


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
    logger.debug("Received JD analysis request, length=%d", len(raw_text))

    # JobIntelligenceExtractionError propagates to the route handlers
    # below, which translate it into an HTTP 502 — there is no
    # deterministic fallback for a failed extraction (see builder.py).
    job_intelligence, company_intelligence = await build_job_intelligence(db, user.id, raw_text, company, role)
    target_profile = build_target_profile(job_intelligence, company_intelligence)

    logger.debug(
        "Job Intelligence extracted %d required, %d implicit, %d nice-to-have, %d architecture topics "
        "(extraction_quality=%s).",
        len(job_intelligence.enriched_required_skills),
        len(job_intelligence.enriched_implicit_skills),
        len(job_intelligence.enriched_nice_to_have),
        len(job_intelligence.architecture_topics),
        job_intelligence.extraction_quality.label,
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
    logger.debug(
        "Gap analysis complete: %d have, %d partial, %d missing, %d total estimated weeks.",
        len(report.have), len(report.partial), len(report.missing), report.estimated_weeks,
    )

    category_breakdown = compute_category_breakdown(report.have, report.partial, report.missing)
    overall_match = compute_overall_match(
        target_profile.job_intelligence.canonical_skills_map, report.have, report.partial, report.missing,
    )
    context = build_narrative_context(
        role=resolved_role,
        company=resolved_company,
        have=report.have,
        partial=report.partial,
        missing=report.missing,
        priority_order=report.priority_order,
        category_breakdown=category_breakdown,
        overall_match=overall_match,
        job_interview_focus_areas=target_profile.job_intelligence.interview_focus_areas,
    )

    degraded = False
    try:
        analysis = await generate_narrative_analysis(context)
    except InterpretationError as e:
        logger.warning("Narrative generation degraded, using fallback: %s", e)
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
    logger.info(
        "Skill gap analysis + narrative persisted (JobDescription id=%s, GapAnalysisResult id=%s).",
        job_description.id, gap_result_row.id,
    )

    await trigger_identity_refresh(db, user.id, "job description analysis")

    return response


async def _get_or_build_gap_result_for_job_intelligence(
    db,
    user: User,
    job_intelligence,
    company_intelligence,
    regenerate: bool,
) -> GapAnalysisResultRow:
    """The core of the new "select an existing parsed job" flow. Never
    re-extracts the JD (that's Job Intelligence's job, already done) —
    only ever runs the Comparison Engine + narrative over a profile that
    already exists. Reads back the latest GapAnalysisResultRow for this
    job_intelligence_id unless the caller explicitly asks to regenerate,
    same caching pattern used by /resume/coherence, /resume/tailor, and
    /projects/portfolio-narrative elsewhere in this codebase.
    """
    job_intelligence_uuid = UUID(job_intelligence.id)

    if not regenerate:
        cached = await _get_latest_gap_result_row(db, job_intelligence_uuid)
        if cached is not None:
            return cached

    target_profile = build_target_profile(job_intelligence, company_intelligence)

    report = await analyze_skill_gap(db, user.id, target_profile.job_intelligence)
    logger.debug(
        "Gap analysis (existing job_intelligence_id=%s) complete: %d have, %d partial, %d missing.",
        job_intelligence_uuid, len(report.have), len(report.partial), len(report.missing),
    )

    category_breakdown = compute_category_breakdown(report.have, report.partial, report.missing)
    overall_match = compute_overall_match(
        target_profile.job_intelligence.canonical_skills_map, report.have, report.partial, report.missing,
    )
    context = build_narrative_context(
        role=job_intelligence.role,
        company=job_intelligence.company,
        have=report.have,
        partial=report.partial,
        missing=report.missing,
        priority_order=report.priority_order,
        category_breakdown=category_breakdown,
        overall_match=overall_match,
        job_interview_focus_areas=target_profile.job_intelligence.interview_focus_areas,
    )

    degraded = False
    try:
        analysis = await generate_narrative_analysis(context)
    except InterpretationError as e:
        logger.warning("Narrative generation degraded, using fallback: %s", e)
        analysis = fallback_narrative(context)
        degraded = True

    gap_result_row = GapAnalysisResultRow(
        user_id=user.id,
        job_intelligence_id=job_intelligence_uuid,
        company_intelligence_id=(
            UUID(company_intelligence.id) if company_intelligence and company_intelligence.id else None
        ),
        report_json=report.model_dump(mode="json"),
        category_breakdown_json={"items": category_breakdown},
        overall_match_json=overall_match,
        narrative_json=analysis.model_dump(mode="json"),
        analysis_degraded=degraded,
        created_at=datetime.now(timezone.utc),
    )
    db.add(gap_result_row)
    await db.commit()
    await db.refresh(gap_result_row)

    await trigger_identity_refresh(db, user.id, "job description analysis")

    return gap_result_row


@router.get("/by-intelligence/{job_intelligence_id}", response_model=SkillGapForJobResponse)
async def get_skill_gap_for_job_intelligence(
    job_intelligence_id: UUID,
    regenerate: bool = False,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Skill Gap's actual entry point going forward: the user selects an
    already-parsed Job Intelligence profile (from GET /job-intelligence)
    and this runs — or reads back a cached — comparison against their
    Engineering Identity. No JD text, no manual configuration; the only
    input is which existing profile to compare against.
    """
    job_intelligence = await get_job_intelligence(db, job_intelligence_id)
    if job_intelligence is None:
        raise HTTPException(status_code=404, detail="Job intelligence profile not found")

    company_intelligence = await get_company_intelligence_by_source_hash(
        db, current_user.id, job_intelligence.source_text_hash,
    )

    gap_row = await _get_or_build_gap_result_for_job_intelligence(
        db, current_user, job_intelligence, company_intelligence, regenerate,
    )

    return SkillGapForJobResponse(
        job_intelligence=job_intelligence,
        company_intelligence=company_intelligence,
        report=gap_row.report_json,
        category_breakdown=[CategoryScore(**c) for c in gap_row.category_breakdown_json.get("items", [])],
        overall_match=OverallMatch(**gap_row.overall_match_json),
        analysis=NarrativeAnalysis(**gap_row.narrative_json),
        analysis_degraded=gap_row.analysis_degraded,
        generated_at=gap_row.created_at.isoformat(),
    )


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

    # SECURITY FIX (Phase 1 §1.4 — validate uploaded documents + input-
    # size limits).
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum allowed size of {settings.max_upload_bytes // (1024 * 1024)}MB.",
        )
    if not raw_bytes.lstrip().startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Uploaded file does not appear to be a valid PDF.")

    raw_text = extract_text_from_pdf(BytesIO(raw_bytes))
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in this PDF.")
    if len(raw_text) > settings.max_paste_text_chars:
        raw_text = raw_text[: settings.max_paste_text_chars]

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