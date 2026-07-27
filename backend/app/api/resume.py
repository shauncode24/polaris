from fastapi import APIRouter, HTTPException, UploadFile, Depends
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_from_query
from app.core.database import get_db
from app.models.facts import (
    User, Resume, Experience, Project, Education, Certificate, JobDescription
)
from app.models.inference import ResumeReview, ResumeAnalysis
from app.models.structure import Skill, SkillAlias
from app.services.resume.ingestion import ingest_resume
from app.services.resume.reviewer import generate_resume_review
from app.services.resume.ats_checks import run_ats_checks

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/upload")
async def upload_resume(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw_bytes = await file.read()
    result = await ingest_resume(raw_bytes, db, current_user, filename=file.filename)
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
    db: AsyncSession = Depends(get_db),
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
    return report


@router.get("/download")
async def download_resume(
    current_user: User = Depends(get_current_user_from_query),
    db: AsyncSession = Depends(get_db),
):
    """Serve the latest resume PDF bytes for inline preview.

    Accepts an optional ?token=... query param as a fallback so that
    browser <embed> tags (which cannot set Authorization headers) can
    still authenticate.  The standard bearer header is preferred and
    validated first by get_current_user; this param is only a UX
    convenience for the preview embed.
    """
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

    # ── Latest resume ───────────────────────────────────────────────────────
    resumes_result = await db.execute(
        select(Resume)
        .where(Resume.user_id == uid)
        .order_by(Resume.created_at.desc())
    )
    resumes = list(resumes_result.scalars().all())

    if not resumes:
        return {"has_resume": False}

    latest = resumes[0]

    # ── Counts (snapshot) ───────────────────────────────────────────────────
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

    # Skill count: unique skills extracted from latest resume (via resume_id join)
    skill_count_result = await db.execute(
        select(func.count(func.distinct(Experience.id)))
        .where(Experience.user_id == uid, Experience.resume_id == latest.id)
    )
    resume_exp_count = skill_count_result.scalar_one()

    # Count skills unique to latest resume using the snapshot approach —
    # use raw_text word count as proxy for "skills" until a better signal exists
    # Real skill count: count Skill rows linked via SkillEvidence → Experience → latest resume
    from app.models.inference import SkillEvidence
    from app.models.structure import Skill
    skill_names_result = await db.execute(
        select(func.count(func.distinct(SkillEvidence.skill_id)))
        .join(Experience, (SkillEvidence.source_id == Experience.id) & (SkillEvidence.source_type == "experience"))
        .where(Experience.user_id == uid, Experience.resume_id == latest.id)
    )
    resume_skill_count = skill_names_result.scalar_one()

    # ── ATS health flags ────────────────────────────────────────────────────
    ats_flags = run_ats_checks(latest.raw_text)

    # ── Latest review (LLM) ─────────────────────────────────────────────────
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
        }

    # ── Latest deterministic analysis ────────────────────────────────────────
    analysis_result = await db.execute(
        select(ResumeAnalysis)
        .where(ResumeAnalysis.user_id == uid)
        .order_by(ResumeAnalysis.created_at.desc())
        .limit(1)
    )
    analysis_row = analysis_result.scalar_one_or_none()
    latest_analysis = analysis_row.analysis_json if analysis_row else None

    # ── Version history ─────────────────────────────────────────────────────
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
    versions = list(reversed(versions))  # newest first

    # ── Profile consistency ──────────────────────────────────────────────────
    # All skills the user has in SkillEvidence (from any source)
    all_skills_result = await db.execute(
        select(Skill.name)
        .join(SkillEvidence, SkillEvidence.skill_id == Skill.id)
        .where(SkillEvidence.source_type.in_(["project", "experience"]))
        .distinct()
    )
    all_profile_skills = set(r[0] for r in all_skills_result.fetchall())

    # Skills linked to latest resume experiences
    resume_skills_result = await db.execute(
        select(Skill.name)
        .join(SkillEvidence, SkillEvidence.skill_id == Skill.id)
        .join(Experience, (SkillEvidence.source_id == Experience.id) & (SkillEvidence.source_type == "experience"))
        .where(Experience.user_id == uid, Experience.resume_id == latest.id)
        .distinct()
    )
    resume_skills = set(r[0] for r in resume_skills_result.fetchall())

    missing_from_resume = sorted(all_profile_skills - resume_skills)

    # ── Resume vs jobs ───────────────────────────────────────────────────────
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
            "profile_skill_count": len(all_profile_skills),
            "resume_skill_count": len(resume_skills),
            "missing_from_resume": missing_from_resume[:10],
        },
        "resume_vs_jobs": resume_vs_jobs,
    }