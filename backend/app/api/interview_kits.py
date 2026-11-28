"""The interview kit for one job: generate it, read it, and match its evidence
again. Practice and the study plan are in interview.py.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.background_jobs import run_in_background
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.schemas.interview.kit_view import KitPage
from app.services.interview.kit_evidence import remap_kit
from app.services.interview.kit_generation import generate_interview_kit
from app.services.interview.kit_store import get_kit, save_new_kit
from app.services.interview.kit_view import kit_page
from app.services.job_intelligence.builder import get_job_intelligence

router = APIRouter(prefix="/interview/kits", tags=["interview-kits"])

_JOB_NOT_FOUND = "Job not found."
_KIT_NOT_FOUND = "That interview kit doesn't exist."


@router.get("/{job_intelligence_id}", response_model=KitPage)
async def get_interview_kit(
    job_intelligence_id: UUID,
    version: int | None = Query(None, ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = await kit_page(db, current_user.id, job_intelligence_id, version)
    if page is None:
        raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND if version is None else _KIT_NOT_FOUND)
    return page


@router.post("/{job_intelligence_id}", response_model=KitPage)
async def create_interview_kit(
    job_intelligence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generates the next version of the kit for this job. Earlier versions, and
    the practice on them, are kept.
    """
    user_id = current_user.id
    if await get_job_intelligence(db, user_id, job_intelligence_id) is None:
        raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)

    async def work(job_db: AsyncSession):
        draft = await generate_interview_kit(job_db, user_id, job_intelligence_id)
        saved = draft and await save_new_kit(job_db, user_id, job_intelligence_id, draft)
        if saved is None:  # the job was deleted meanwhile
            raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)
        return await kit_page(job_db, user_id, job_intelligence_id, saved.kit.version)

    # Not refused when the day's AI calls are used up: the kit can still be made
    # in standard wording, and says so.
    return await run_in_background(
        user_id, "interview_kit", work, inputs=(job_intelligence_id,), needs_model=False,
    )


@router.post("/{job_intelligence_id}/versions/{version}/evidence", response_model=KitPage)
async def match_kit_evidence(
    job_intelligence_id: UUID,
    version: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Matches a saved kit's questions against the record as it is now."""
    user_id = current_user.id
    if await get_kit(db, user_id, job_intelligence_id, version) is None:
        raise HTTPException(status_code=404, detail=_KIT_NOT_FOUND)

    async def work(job_db: AsyncSession):
        if await remap_kit(job_db, user_id, job_intelligence_id, version) is None:
            raise HTTPException(status_code=404, detail=_KIT_NOT_FOUND)
        return await kit_page(job_db, user_id, job_intelligence_id, version)

    return await run_in_background(
        user_id, "interview_kit_evidence", work, inputs=(job_intelligence_id, version), needs_model=False,
    )
