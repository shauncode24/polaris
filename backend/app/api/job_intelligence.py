from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.models.job_intelligence import JobIntelligenceProfileRow
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceSummary
from app.schemas.job_intelligence.target_profile import TargetProfile
from app.services.company_intelligence.reader import get_company_intelligence_by_source_hash
from app.services.job_intelligence.builder import (
    JobIntelligenceExtractionError,
    build_job_intelligence,
    get_job_intelligence,
)
from app.services.resume.pdf_parser import extract_text_from_pdf
from app.services.target_profile.builder import build_target_profile

router = APIRouter(prefix="/job-intelligence", tags=["job-intelligence"])


class JobIntelligenceRequest(BaseModel):
    raw_text: str
    company: str | None = None
    role: str | None = None


@router.post("/analyze", response_model=TargetProfile)
async def analyze_job_intelligence(
    payload: JobIntelligenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns the full TargetProfile (Job Intelligence + Company
    Intelligence) from the single combined extraction call — this is
    the Job & Company Intelligence module's own entry point, entirely
    separate from /jobs/analyze (Comparison Engine)."""
    try:
        job_profile, company_profile = await build_job_intelligence(
            db, current_user.id, payload.raw_text, payload.company, payload.role,
        )
    except JobIntelligenceExtractionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return build_target_profile(job_profile, company_profile)


@router.post("/analyze-pdf", response_model=TargetProfile)
async def analyze_job_intelligence_pdf(
    file: UploadFile = File(...),
    company: str | None = Form(None),
    role: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw_bytes = await file.read()
    raw_text = extract_text_from_pdf(BytesIO(raw_bytes))
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in this PDF.")
    try:
        job_profile, company_profile = await build_job_intelligence(db, current_user.id, raw_text, company, role)
    except JobIntelligenceExtractionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return build_target_profile(job_profile, company_profile)


@router.get("/{job_intelligence_id}", response_model=TargetProfile)
async def get_job_intelligence_by_id(
    job_intelligence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job_profile = await get_job_intelligence(db, job_intelligence_id)
    if job_profile is None:
        raise HTTPException(status_code=404, detail="Job intelligence profile not found")
    company_profile = await get_company_intelligence_by_source_hash(
        db, current_user.id, job_profile.source_text_hash,
    )
    return build_target_profile(job_profile, company_profile)


@router.get("", response_model=list[JobIntelligenceSummary])
async def list_job_intelligence(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobIntelligenceProfileRow)
        .where(JobIntelligenceProfileRow.user_id == current_user.id)
        .order_by(JobIntelligenceProfileRow.created_at.desc())
    )
    summaries = []
    for row in result.scalars().all():
        pj = row.profile_json or {}
        seniority = pj.get("seniority_signal") or {}
        quality = pj.get("extraction_quality") or {}
        summaries.append(JobIntelligenceSummary(
            id=str(row.id),
            role=pj.get("role"),
            company=pj.get("company"),
            seniority_level=seniority.get("level", "unspecified"),
            extraction_quality_label=quality.get("label", "Low"),
            created_at=row.created_at.isoformat(),
        ))
    return summaries