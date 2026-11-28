"""The resume tailored to one job: generate it, read it, and save the user's
choices on it.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.background_jobs import run_in_background
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.schemas.resume.tailored_editor import ResumeChanges, ResumeEditorView
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.resume.editor import ResumeChangeError, change_resume, editor_view
from app.services.resume.generation import generate_tailored_resume
from app.services.resume.tailored_store import save_new_version

router = APIRouter(prefix="/tailored-resumes", tags=["tailored-resumes"])

_JOB_NOT_FOUND = "Job not found."
_VERSION_NOT_FOUND = "That resume doesn't exist."


@router.get("/{job_intelligence_id}", response_model=ResumeEditorView)
async def get_tailored_resume(
    job_intelligence_id: UUID,
    version: int | None = Query(None, ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    view = await editor_view(db, current_user.id, job_intelligence_id, version)
    if view is None:
        raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND if version is None else _VERSION_NOT_FOUND)
    return view


@router.post("/{job_intelligence_id}", response_model=ResumeEditorView)
async def create_tailored_resume(
    job_intelligence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generates the next version for this job."""
    user_id = current_user.id
    if await get_job_intelligence(db, user_id, job_intelligence_id) is None:
        raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)

    async def work(job_db: AsyncSession):
        selection = await generate_tailored_resume(job_db, user_id, job_intelligence_id)
        row = selection and await save_new_version(job_db, user_id, job_intelligence_id, selection.document)
        if row is None:  # the job was deleted meanwhile
            raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)
        return await editor_view(job_db, user_id, job_intelligence_id, row.version)

    # Not refused when the day's AI calls are used up: the resume can still be
    # made in the user's own wording, and says so.
    return await run_in_background(
        user_id, "tailored_resume", work, inputs=(job_intelligence_id,), needs_model=False,
    )


@router.patch("/{job_intelligence_id}/versions/{version}", response_model=ResumeEditorView)
async def change_tailored_resume(
    job_intelligence_id: UUID,
    version: int,
    changes: ResumeChanges,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accepts, rejects or edits lines, and reorders sections."""
    try:
        view = await change_resume(db, current_user.id, job_intelligence_id, version, changes)
    except ResumeChangeError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    if view is None:
        raise HTTPException(status_code=404, detail=_VERSION_NOT_FOUND)
    return view
