from fastapi import APIRouter, HTTPException, UploadFile, Depends
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_from_query
from app.core.database import get_db
from app.models.facts import (
    User, Resume, Experience, Project, Education, Certificate, JobDescription,
    GithubSnapshot, LeetcodeSnapshot
)
from app.models.inference import ResumeReview, ResumeAnalysis, SkillEvidence
from app.models.structure import Skill, SkillAlias
from app.services.resume.ingestion import ingest_resume
from app.services.resume.reviewer import generate_resume_review
from app.services.resume.ats_checks import run_ats_checks


from uuid import UUID
from app.schemas.resume_coherence import CoherenceReport
from app.schemas.resume_tailoring import TailoringReport
from app.schemas.resume_evolution import EvolutionReport
from app.services.resume.coherence_narrative import generate_coherence_report
from app.services.resume.tailoring_llm import generate_tailoring_report
from app.services.resume.evolution import build_evolution_report

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

    # Deterministically synchronize skills from raw text if missing to avoid LLM token waste
    ev_check_result = await db.execute(
        select(func.count(SkillEvidence.id))
        .join(Experience, (SkillEvidence.source_id == Experience.id) & (SkillEvidence.source_type == "experience"))
        .where(Experience.user_id == uid, Experience.resume_id == latest.id)
    )
    if ev_check_result.scalar_one() == 0:
        from app.services.resume.ingestion import sync_resume_skills_deterministically
        from sqlalchemy import delete
        try:
            await sync_resume_skills_deterministically(db, latest, uid)
            # Clear cached ResumeAnalysis rows for this user to trigger a fresh analysis run with full skills
            await db.execute(delete(ResumeAnalysis).where(ResumeAnalysis.user_id == uid))
            await db.commit()
        except Exception as e:
            import traceback
            print("Deterministic skill sync failed:", flush=True)
            traceback.print_exc()

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
    skill_names_result = await db.execute(
        select(func.count(func.distinct(SkillEvidence.skill_id)))
        .join(Experience, (SkillEvidence.source_id == Experience.id) & (SkillEvidence.source_type == "experience"))
        .where(Experience.user_id == uid, Experience.resume_id == latest.id)
    )
    resume_skill_count = skill_names_result.scalar_one()

    # ── Latest deterministic analysis ────────────────────────────────────────
    analysis_result = await db.execute(
        select(ResumeAnalysis)
        .where(ResumeAnalysis.user_id == uid)
        .order_by(ResumeAnalysis.created_at.desc())
        .limit(1)
    )
    analysis_row = analysis_result.scalar_one_or_none()
    
    # Trigger synchronous analysis run if missing, old scoring format, or missing AI role fits
    if not analysis_row or "warnings" not in analysis_row.analysis_json or "role_fit" not in analysis_row.analysis_json:
        from app.services.resume.analysis.engine import run_analysis
        try:
            latest_analysis = await run_analysis(db, uid)
        except Exception:
            latest_analysis = analysis_row.analysis_json if analysis_row else None
    else:
        latest_analysis = analysis_row.analysis_json

    # ── ATS health flags ────────────────────────────────────────────────────
    ats_flags = latest_analysis.get("warnings", []) if latest_analysis else []

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
    # 1. Fetch user's profile skills (GitHub languages, Leetcode, Certificates)
    profile_skills = set()
    
    # GitHub
    gh_rows = await db.execute(
        select(GithubSnapshot.languages).where(GithubSnapshot.user_id == uid)
    )
    for row in gh_rows.fetchall():
        if row[0]:
            profile_skills.update(k.lower() for k in row[0].keys())

    # Leetcode
    lc_ev_rows = await db.execute(
        select(Skill.name)
        .join(LeetcodeSnapshot, (LeetcodeSnapshot.tag == Skill.name) | (LeetcodeSnapshot.tag == Skill.canonical_name))
        .where(LeetcodeSnapshot.user_id == uid)
    )
    profile_skills.update(r[0].lower() for r in lc_ev_rows.fetchall() if r[0])

    # Certificates
    cert_ev_rows = await db.execute(
        select(Certificate.skills).where(Certificate.user_id == uid)
    )
    for row in cert_ev_rows.fetchall():
        if row[0]:
            profile_skills.update(s.lower() for s in row[0])

    # Exclude generic Leetcode algorithmic skills if needed, or keep all profile skills
    from app.services.resume.analysis.engine import EXCLUDED_SKILLS
    profile_skills = {s for s in profile_skills if s not in EXCLUDED_SKILLS}

    # 2. Fetch all skills that are present in the latest resume (experiences, projects, and parsed skills)
    resume_skills = set()
    
    # Skills from experiences
    exp_skills = await db.execute(
        select(Skill.canonical_name)
        .join(SkillEvidence, SkillEvidence.skill_id == Skill.id)
        .join(Experience, (SkillEvidence.source_id == Experience.id) & (SkillEvidence.source_type == "experience"))
        .where(Experience.resume_id == latest.id)
    )
    resume_skills.update(r[0].lower() for r in exp_skills.fetchall() if r[0])

    # Skills from projects
    proj_skills = await db.execute(
        select(Skill.canonical_name)
        .join(SkillEvidence, SkillEvidence.skill_id == Skill.id)
        .join(Project, (SkillEvidence.source_id == Project.id) & (SkillEvidence.source_type == "project"))
        .where(Project.resume_id == latest.id)
    )
    resume_skills.update(r[0].lower() for r in proj_skills.fetchall() if r[0])

    # Skills from parsed general skills section
    from app.services.resume.ingestion import extract_skills_from_text
    from app.services.resume.skill_classifier import resolve_skills
    parsed_skills = extract_skills_from_text(latest.raw_text)
    if parsed_skills:
        resolved_parsed = await resolve_skills(set(parsed_skills), db)
        resume_skills.update(canonical.lower() for canonical in resolved_parsed.values() if canonical)

    # 3. Compute consistency
    all_profile_skills = profile_skills | resume_skills
    display_names = {}
    if all_profile_skills:
        skill_rows = await db.execute(
            select(Skill.canonical_name, Skill.name).where(Skill.canonical_name.in_(list(all_profile_skills)))
        )
        for canonical, name in skill_rows.fetchall():
            display_names[canonical.lower()] = name
            display_names[name.lower()] = name

    missing_keys = profile_skills - resume_skills
    missing_from_resume = sorted([display_names.get(k, k.title()) for k in missing_keys])


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

    # ── Role compatibility & Cross-source gaps ───────────────────────────────
    from app.services.resume.analysis.evidence import analyze_evidence
    from app.services.resume.analysis.role_fit import compute_role_fit
    from app.services.resume.analysis.coverage import analyze_cross_source_coverage

    evidence_res = await analyze_evidence(db, uid, latest.id)
    role_fit = None
    if latest_analysis and isinstance(latest_analysis, dict):
        role_fit = latest_analysis.get("role_fit")
    if not role_fit:
        role_fit = compute_role_fit(evidence_res.get("skills", []))

    coverage_gaps = await analyze_cross_source_coverage(db, uid, latest.id)

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
        "role_fit": role_fit,
        "coverage_gaps": coverage_gaps,
    }

@router.get("/coherence", response_model=CoherenceReport)
async def get_resume_coherence(
    target_role: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.created_at.desc()).limit(1)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=400, detail="No uploaded resume found — upload a resume first.")
    return await generate_coherence_report(db, current_user.id, resume.id, target_role)


@router.get("/tailor/{job_description_id}", response_model=TailoringReport)
async def get_resume_tailoring(
    job_description_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.created_at.desc()).limit(1)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=400, detail="No uploaded resume found — upload a resume first.")
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