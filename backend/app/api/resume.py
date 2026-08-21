from fastapi import APIRouter, HTTPException, UploadFile, Depends
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_from_query
from app.core.database import get_db
from app.core.settings import settings
from app.models.facts import (
    User, Resume, Experience, Project, Education, Certificate, JobDescription,
    GithubSnapshot, LeetcodeSnapshot
)
from app.models.inference import ResumeReview, ResumeAnalysis, SkillEvidence
from app.models.structure import Skill, SkillAlias
from app.services.resume.ingestion import ingest_resume
from app.services.resume.reviewer import generate_resume_review
from app.services.resume.ats_checks import run_ats_checks
from app.services.identity.role_fit import get_role_fit
from app.services.identity.role_fit_scoping import build_scoped_skill_evidence, RESUME_SOURCE_TYPES


from uuid import UUID
from app.schemas.resume.resume_coherence import CoherenceReport
from app.schemas.resume.resume_tailoring import TailoringReport
from app.schemas.resume.resume_evolution import EvolutionReport
from app.services.resume.coherence_narrative import generate_coherence_report, get_cached_coherence_report
from app.services.resume.tailoring_llm import generate_tailoring_report, get_cached_tailoring_report
from app.services.resume.evolution import build_evolution_report

from app.services.identity.identity_refresh import trigger_identity_refresh

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/upload")
async def upload_resume(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw_bytes = await file.read()

    # SECURITY FIX (Phase 1 §1.4 — validate uploaded documents + input-
    # size limits): previously any file, of any size or type, was handed
    # straight to the PDF parser. Now rejected up front with a clear 4xx
    # instead of failing deep inside pdfplumber (or silently accepting
    # something that isn't actually a resume).
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum allowed size of {settings.max_upload_bytes // (1024 * 1024)}MB.",
        )
    if not raw_bytes.lstrip().startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Uploaded file does not appear to be a valid PDF.")

    result = await ingest_resume(raw_bytes, db, current_user, filename=file.filename)
    # Freshness fix: keep Engineering Identity current the instant new
    # resume data lands, instead of only on a manual POST /identity/refresh.
    await trigger_identity_refresh(db, current_user.id, "resume upload")
    return result

@router.post("/review")
async def review_resume(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        report = await generate_resume_review(db, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return report


@router.post("/analyze")
async def analyze_resume(
    job_description_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Run the full deterministic Resume Analysis Engine and persist the result."""
    try:
        from app.services.resume.analysis.engine import run_analysis
        report = await run_analysis(
            db,
            current_user.id,
            job_description_id=job_description_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # This is the endpoint that actually produces resume_score/grade —
    # the field IdentityFacts reads — so it gets its own refresh trigger
    # distinct from the raw upload above.
    await trigger_identity_refresh(db, current_user.id, "resume analysis")
    return report


@router.get("/download")
async def download_resume(
    current_user: User = Depends(get_current_user_from_query),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    resume = result.scalar_one_or_none()

    if resume is None:
        raise HTTPException(status_code=404, detail="No resume uploaded yet.")

    if resume.raw_bytes is None:
        raise HTTPException(
            status_code=404,
            detail="PDF not stored — please re-upload your resume to enable preview.",
        )

    filename = resume.filename or "resume.pdf"
    return Response(
        content=resume.raw_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=300",
        },
    )


@router.get("/workspace")
async def get_resume_workspace(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Single aggregated endpoint for the Resume page."""
    uid = current_user.id

    resumes_result = await db.execute(
        select(Resume)
        .where(Resume.user_id == uid)
        .order_by(Resume.created_at.desc())
    )
    resumes = list(resumes_result.scalars().all())

    if not resumes:
        return {"has_resume": False}

    latest = resumes[0]

    ev_check_result = await db.execute(
        select(func.count(SkillEvidence.id))
        .join(Experience, (SkillEvidence.source_id == Experience.id) & (SkillEvidence.source_type == "experience"))
        .where(Experience.user_id == uid, Experience.resume_id == latest.id)
    )
    needs_skill_sync = ev_check_result.scalar_one() == 0

    async def count(model, extra_filter=None):
        stmt = select(func.count()).select_from(model).where(model.user_id == uid)
        if extra_filter is not None:
            stmt = stmt.where(extra_filter)
        r = await db.execute(stmt)
        return r.scalar_one()

    exp_count = await count(Experience)
    proj_count = await count(Project)
    edu_count = await count(Education)
    cert_count = await count(Certificate)

    skill_count_result = await db.execute(
        select(func.count(func.distinct(Experience.id)))
        .where(Experience.user_id == uid, Experience.resume_id == latest.id)
    )
    resume_exp_count = skill_count_result.scalar_one()

    skill_names_result = await db.execute(
        select(func.count(func.distinct(SkillEvidence.skill_id)))
        .join(Experience, (SkillEvidence.source_id == Experience.id) & (SkillEvidence.source_type == "experience"))
        .where(Experience.user_id == uid, Experience.resume_id == latest.id)
    )
    resume_skill_count = skill_names_result.scalar_one()

    analysis_result = await db.execute(
        select(ResumeAnalysis)
        .where(
            ResumeAnalysis.user_id == uid,
            ResumeAnalysis.resume_id == latest.id,
        )
        .order_by(ResumeAnalysis.created_at.desc())
        .limit(1)
    )
    analysis_row = analysis_result.scalar_one_or_none()

    latest_analysis = analysis_row.analysis_json if analysis_row else None
    needs_analysis = (
        latest_analysis is None
        or "warnings" not in latest_analysis
        or "role_fit" not in latest_analysis
    )

    ats_flags = latest_analysis.get("warnings", []) if latest_analysis else []

    review_result = await db.execute(
        select(ResumeReview)
        .where(ResumeReview.user_id == uid, ResumeReview.resume_id == latest.id)
        .order_by(ResumeReview.created_at.desc())
        .limit(1)
    )
    review_row = review_result.scalar_one_or_none()
    latest_review = None
    if review_row:
        rj = review_row.review_json
        latest_review = {
            "overall_score": rj.get("overall_score"),
            "stats": rj.get("stats"),
            "summary": rj.get("summary"),
            "strengths": rj.get("strengths", []),
            "top_priority_fixes": rj.get("top_priority_fixes", []),
            "bullet_reviews": rj.get("bullet_reviews", []),
            "created_at": review_row.created_at.isoformat(),
            "analysis_degraded": rj.get("analysis_degraded", False),
        }

    versions = []
    for idx, r in enumerate(reversed(resumes)):
        v_num = idx + 1
        versions.append({
            "id": str(r.id),
            "version": f"v{v_num}",
            "filename": r.filename,
            "created_at": r.created_at.isoformat(),
            "is_current": r.id == latest.id,
        })
    versions = list(reversed(versions))

    jobs_result = await db.execute(
        select(JobDescription)
        .where(
            JobDescription.user_id == uid,
            JobDescription.analysis_result.isnot(None),
        )
        .order_by(JobDescription.created_at.desc())
        .limit(5)
    )
    jobs = list(jobs_result.scalars().all())

    resume_vs_jobs = [
        {
            "id": str(j.id),
            "company": j.company or "Unknown",
            "role": j.role or "Unknown",
            "match_pct": round(j.analysis_result.get("overall_match_percentage", 0))
            if j.analysis_result
            else None,
        }
        for j in jobs
    ]

    from app.services.resume.analysis.evidence import analyze_evidence
    from app.services.resume.analysis.coverage import analyze_cross_source_coverage

    evidence_res = await analyze_evidence(db, uid, latest.id)

    # Role Compatibility — deliberately, entirely LLM-generated (fix #2).
    # Previously computed via a deterministic category-coverage formula
    # (compute_role_fit) fed the source-count-bucketed evidence from
    # analyze_evidence(); now it goes through the single shared LLM-based
    # get_role_fit(), scoped to this resume's own project/experience evidence.
    role_fit = None
    if latest_analysis and isinstance(latest_analysis, dict):
        role_fit = latest_analysis.get("role_fit")
    if not role_fit:
        # FIX (cross-user evidence leak): user_id now required.
        resume_scoped_evidence = await build_scoped_skill_evidence(db, uid, RESUME_SOURCE_TYPES)
        role_fit_results = await get_role_fit(resume_scoped_evidence, scope="resume_only")
        role_fit = [r.model_dump() for r in role_fit_results]

    coverage_gaps = await analyze_cross_source_coverage(db, uid, latest.id)

    missing_from_resume_keys = (
        {g["skill"].lower() for g in coverage_gaps.get("github_gaps", [])}
        | {g["skill"].lower() for g in coverage_gaps.get("leetcode_gaps", [])}
        | {g["skill"].lower() for g in coverage_gaps.get("certificate_gaps", [])}
    )
    resume_skill_keys = {s["canonical"].lower() for s in evidence_res.get("skills", []) if s.get("canonical")}
    missing_from_resume_keys -= resume_skill_keys  # a gap already on the resume isn't a gap

    missing_from_resume = sorted(k.title() for k in missing_from_resume_keys)
    profile_skill_count = len(missing_from_resume_keys | resume_skill_keys)

    return {
        "has_resume": True,
        "current_resume": {
            "id": str(latest.id),
            "filename": latest.filename or "resume.pdf",
            "created_at": latest.created_at.isoformat(),
            "has_pdf": latest.raw_bytes is not None,
        },
        "versions": versions,
        "snapshot": {
            "experience": exp_count,
            "projects": proj_count,
            "education": edu_count,
            "certificates": cert_count,
            "skills": resume_skill_count,
        },
        "ats_flags": ats_flags,
        "latest_review": latest_review,
        "latest_analysis": latest_analysis,
        "profile_consistency": {
            "profile_skill_count": profile_skill_count,
            "resume_skill_count": evidence_res.get("total_skills", 0),
            "missing_from_resume": missing_from_resume[:10],
        },
        "resume_vs_jobs": resume_vs_jobs,
        "role_fit": role_fit,
        "coverage_gaps": coverage_gaps,
        "needs_skill_sync": needs_skill_sync,
        "needs_analysis": needs_analysis,
    }

@router.get("/coherence", response_model=CoherenceReport)
async def get_resume_coherence(
    target_role: str | None = None,
    regenerate: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.created_at.desc()).limit(1)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=400, detail="No uploaded resume found — upload a resume first.")

    if not regenerate:
        cached = await get_cached_coherence_report(db, resume.id, target_role)
        if cached is not None:
            return cached

    return await generate_coherence_report(db, current_user.id, resume.id, target_role)


@router.get("/tailor/{job_description_id}", response_model=TailoringReport)
async def get_resume_tailoring(
    job_description_id: UUID,
    regenerate: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.created_at.desc()).limit(1)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=400, detail="No uploaded resume found — upload a resume first.")

    if not regenerate:
        cached = await get_cached_tailoring_report(db, resume.id, job_description_id)
        if cached is not None:
            return cached

    try:
        return await generate_tailoring_report(db, current_user.id, resume.id, job_description_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/evolution", response_model=EvolutionReport)
async def get_resume_evolution(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await build_evolution_report(db, current_user.id)