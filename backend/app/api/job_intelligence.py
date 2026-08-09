# backend/app/api/job_intelligence.py
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
from app.schemas.job_intelligence import JobIntelligenceProfile
from app.services.job_intelligence.builder import build_job_intelligence, get_job_intelligence
from app.services.resume.pdf_parser import extract_text_from_pdf

router = APIRouter(prefix="/job-intelligence", tags=["job-intelligence"])


class JobIntelligenceRequest(BaseModel):
    raw_text: str
    company: str | None = None
    role: str | None = None


@router.post("/analyze", response_model=JobIntelligenceProfile)
async def analyze_job_intelligence(
    payload: JobIntelligenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job_profile, _company_profile = await build_job_intelligence(
        db, current_user.id, payload.raw_text, payload.company, payload.role,
    )
    return job_profile


@router.post("/analyze-pdf", response_model=JobIntelligenceProfile)
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
    job_profile, _company_profile = await build_job_intelligence(db, current_user.id, raw_text, company, role)
    return job_profile


@router.get("/{job_intelligence_id}", response_model=JobIntelligenceProfile)
async def get_job_intelligence_by_id(
    job_intelligence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_job_intelligence(db, job_intelligence_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Job intelligence profile not found")
    return profile


@router.get("", response_model=list[JobIntelligenceProfile])
async def list_job_intelligence(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobIntelligenceProfileRow)
        .where(JobIntelligenceProfileRow.user_id == current_user.id)
        .order_by(JobIntelligenceProfileRow.created_at.desc())
    )
    profiles = []
    for row in result.scalars().all():
        p = JobIntelligenceProfile.model_validate(row.profile_json)
        p.id = str(row.id)
        profiles.append(p)
    return profiles