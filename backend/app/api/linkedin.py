import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.background_jobs import run_in_background
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.schemas.linkedin.linkedin import LinkedInIngestRequest, LinkedInIngestResult, LinkedInWorkspace
from app.services.evidence.state import touch_evidence
from app.services.identity.identity_refresh import trigger_identity_refresh
from app.services.linkedin.linkedin_ingestion import (
    LinkedInExtractionError,
    get_latest_linkedin_profile,
    ingest_linkedin_profile,
)

router = APIRouter(prefix="/linkedin", tags=["linkedin"])


@router.post("/ingest", response_model=LinkedInIngestResult)
async def ingest_linkedin(
    payload: LinkedInIngestRequest,
    current_user: User = Depends(get_current_user),
):
    """Ingests user-pasted LinkedIn profile text (never scraped — see
    Phase 4 scope). Reconciles into the same Experience/Education/
    SkillEvidence tables Resume ingestion writes to, so LinkedIn feeds
    the canonical Polaris Identity as evidence rather than as a
    parallel, competing identity source.
    """
    user_id = current_user.id

    async def work(job_db: AsyncSession):
        user = await job_db.get(User, user_id)
        try:
            result = await ingest_linkedin_profile(job_db, user, payload.raw_text)
        except LinkedInExtractionError as e:
            raise HTTPException(status_code=502, detail=str(e))

        await touch_evidence(job_db, user_id)
        await trigger_identity_refresh(user_id, "linkedin ingestion")
        return result

    text_hash = hashlib.sha256(payload.raw_text.encode()).hexdigest()
    return await run_in_background(user_id, "linkedin_import", work, inputs=(text_hash,))


@router.get("/workspace", response_model=LinkedInWorkspace)
async def get_linkedin_workspace(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_latest_linkedin_profile(db, current_user.id)
    if profile is None:
        return LinkedInWorkspace(has_data=False)

    parsed = profile.parsed_json or {}
    return LinkedInWorkspace(
        has_data=True,
        headline=parsed.get("headline"),
        about=parsed.get("about"),
        skills=parsed.get("skills", []),
        achievements=parsed.get("achievements", []),
        experience_count=len(parsed.get("experience", [])),
        education_count=len(parsed.get("education", [])),
        created_at=profile.created_at.isoformat(),
    )