import hashlib
import io
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, UploadFile, Depends
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.background_jobs import run_in_background
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.settings import settings
from app.models.facts import (
    User, Resume, Experience, Project, Education, Certificate,
    GithubSnapshot, LeetcodeSnapshot
)
from app.models.inference import ResumeReview, ResumeAnalysis, SkillEvidence
from app.models.job_intelligence import GapAnalysisResultRow, JobIntelligenceProfileRow
from app.models.structure import Skill, SkillAlias
from app.services.resume.pdf_parser import PdfParseError, extract_text_from_pdf_bytes
from app.services.resume.docx_parser import extract_text_from_docx
from app.services.resume.ingestion import ingest_resume
from app.services.resume.reviewer import generate_resume_review
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
from app.services.evidence.review import carry_over_reviews
from app.services.evidence.state import touch_evidence
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.projects.reconcile import reconcile_projects

router = APIRouter(prefix="/resume", tags=["resume"])


def _content_disposition(filename: str) -> str:
    """Builds an `inline` Content-Disposition header from a user-supplied
    filename. The plain `filename` is reduced to safe ASCII (no quotes,
    slashes or control characters, so it can't break out of the header),
    and the original name is passed percent-encoded in `filename*`.
    """
    safe = "".join(c if (c.isascii() and (c.isalnum() or c in "._- ")) else "_" for c in filename).strip()
    safe = safe or "resume.pdf"
    return f"inline; filename=\"{safe}\"; filename*=UTF-8''{quote(filename, safe='')}"


def _is_pdf(raw_bytes: bytes) -> bool:
    return raw_bytes.lstrip().startswith(b"%PDF")


def _is_docx(raw_bytes: bytes, filename: str | None) -> bool:
    # .docx is a ZIP container — sniff the ZIP local-file-header magic
    # bytes AND require a .docx extension, so a renamed/other ZIP-based
    # file (e.g. a plain .zip) doesn't get silently misread as a resume.
    looks_like_zip = raw_bytes[:4] == b"PK\x03\x04"
    has_docx_extension = (filename or "").lower().endswith(".docx")
    return looks_like_zip and has_docx_extension


@router.post("/upload")
async def upload_resume(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw_bytes = await file.read()

    # SECURITY FIX (Phase 1 §1.4 — validate uploaded documents + input-
    # size limits): every file, of any size or type, is checked up front
    # with a clear 4xx instead of failing deep inside a parser.
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum allowed size of {settings.max_upload_bytes // (1024 * 1024)}MB.",
        )

    # Phase 4 — DOCX support: the frontend has always advertised
    # accept=".pdf,.docx"; the backend previously rejected everything
    # that wasn't a PDF. Both extractors converge on the same raw_text
    # contract, so everything downstream (extraction, ingestion, skill
    # evidence) is unchanged regardless of which file type was uploaded.
    if _is_pdf(raw_bytes):
        try:
            raw_text = await extract_text_from_pdf_bytes(raw_bytes)
        except PdfParseError as e:
            raise HTTPException(status_code=400, detail=str(e))
        pdf_bytes: bytes | None = raw_bytes
    elif _is_docx(raw_bytes, file.filename):
        try:
            raw_text = extract_text_from_docx(io.BytesIO(raw_bytes))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read this .docx file: {e}")
        pdf_bytes = None
    else:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a valid PDF or a .docx Word document.",
        )

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in the uploaded file.")

    user_id = current_user.id

    async def work(job_db: AsyncSession):
        user = await job_db.get(User, user_id)
        try:
            result = await ingest_resume(raw_text, job_db, user, filename=file.filename, pdf_bytes=pdf_bytes)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Decisions the user already made about these items on earlier uploads
        # (hidden, confirmed, edited) apply to the new rows; then projects are
        # lined up with the user's GitHub repos.
        await carry_over_reviews(job_db, user_id, UUID(result["resume_id"]))
        await reconcile_projects(job_db, user_id)
        await touch_evidence(job_db, user_id)

        # Freshness fix: keep Engineering Identity current the instant new
        # resume data lands, instead of only on a manual POST /identity/refresh.
        await trigger_identity_refresh(job_db, user_id, "resume upload")
        return result

    return await run_in_background(
        user_id, "resume_upload", work, inputs=(hashlib.sha256(raw_bytes).hexdigest(), file.filename),
    )


@router.post("/review")
async def review_resume(current_user: User = Depends(get_current_user)):
    user_id = current_user.id

    async def work(job_db: AsyncSession):
        try:
            return await generate_resume_review(job_db, user_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return await run_in_background(user_id, "resume_review", work)


@router.post("/analyze")
async def analyze_resume(
    job_intelligence_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Run the full deterministic Resume Analysis Engine and persist the result."""
    user_id = current_user.id
    if job_intelligence_id is not None:
        try:
            parsed_job_id = UUID(job_intelligence_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid job_intelligence_id.")
        if await get_job_intelligence(db, user_id, parsed_job_id) is None:
            raise HTTPException(status_code=404, detail="Job not found.")

    async def work(job_db: AsyncSession):
        from app.services.resume.analysis.engine import run_analysis
        try:
            report = await run_analysis(job_db, user_id, job_intelligence_id=job_intelligence_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        # This is the endpoint that actually produces resume_score/grade —
        # the field IdentityFacts reads — so it gets its own refresh trigger
        # distinct from the raw upload above.
        await trigger_identity_refresh(job_db, user_id, "resume analysis")
        return report

    return await run_in_background(user_id, "resume_analysis", work, inputs=(job_intelligence_id,))


@router.get("/download")
async def download_resume(
    current_user: User = Depends(get_current_user),
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

    return Response(
        content=resume.raw_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": _content_disposition(resume.filename or "resume.pdf"),
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
        select(GapAnalysisResultRow, JobIntelligenceProfileRow)
        .join(JobIntelligenceProfileRow, JobIntelligenceProfileRow.id == GapAnalysisResultRow.job_intelligence_id)
        .where(GapAnalysisResultRow.user_id == uid)
        .order_by(GapAnalysisResultRow.created_at.desc())
    )
    resume_vs_jobs = []
    seen_jobs: set = set()
    for gap, job in jobs_result.all():
        if job.id in seen_jobs:
            continue  # one entry per job: its newest comparison
        seen_jobs.add(job.id)
        profile = job.profile_json or {}
        percentage = (gap.overall_match_json or {}).get("percentage")
        resume_vs_jobs.append({
            "id": str(job.id),
            "company": profile.get("company") or "Unknown",
            "role": profile.get("role") or "Unknown",
            "match_pct": round(percentage) if percentage is not None else None,
        })
        if len(resume_vs_jobs) >= 5:
            break

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
        cached = await get_cached_coherence_report(db, current_user.id, resume.id, target_role)
        if cached is not None:
            return cached

    user_id, resume_id = current_user.id, resume.id

    async def work(job_db: AsyncSession):
        return await generate_coherence_report(job_db, user_id, resume_id, target_role)

    return await run_in_background(user_id, "resume_coherence", work, inputs=(resume_id, target_role))


@router.get("/tailor/{job_intelligence_id}", response_model=TailoringReport)
async def get_resume_tailoring(
    job_intelligence_id: UUID,
    regenerate: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if await get_job_intelligence(db, current_user.id, job_intelligence_id) is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.created_at.desc()).limit(1)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=400, detail="No uploaded resume found — upload a resume first.")

    if not regenerate:
        cached = await get_cached_tailoring_report(db, current_user.id, resume.id, job_intelligence_id)
        if cached is not None:
            return cached

    user_id, resume_id = current_user.id, resume.id

    async def work(job_db: AsyncSession):
        try:
            return await generate_tailoring_report(job_db, user_id, resume_id, job_intelligence_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return await run_in_background(
        user_id, "resume_tailoring", work, inputs=(resume_id, job_intelligence_id),
    )

@router.get("/evolution", response_model=EvolutionReport)
async def get_resume_evolution(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await build_evolution_report(db, current_user.id)