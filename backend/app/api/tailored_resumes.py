"""The resume tailored to one job: generate it, read it, save the user's
choices on it, and download it.
"""
import asyncio
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.background_jobs import run_in_background
from app.api.deps import get_current_user
from app.api.resume import _content_disposition
from app.core.database import get_db
from app.models.facts import User
from app.schemas.resume.tailored_editor import ResumeChanges, ResumeEditorView
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.resume.editor import ResumeChangeError, change_resume, editor_view
from app.services.resume.export import UnsupportedCharacters, file_name, pdf_file, word_file
from app.services.resume.generation import generate_tailored_resume
from app.services.resume.tailored_store import document_of, get_version, save_new_version

router = APIRouter(prefix="/tailored-resumes", tags=["tailored-resumes"])

_JOB_NOT_FOUND = "Job not found."
_VERSION_NOT_FOUND = "That resume doesn't exist."

_FORMATS = {
    "pdf": (pdf_file, "application/pdf"),
    "docx": (word_file, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}


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


@router.get("/{job_intelligence_id}/versions/{version}/export")
async def export_tailored_resume(
    job_intelligence_id: UUID,
    version: int,
    file_format: Literal["pdf", "docx"] = Query(alias="format"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The saved version as a file, holding the wording that is on it."""
    row = await get_version(db, current_user.id, job_intelligence_id, version)
    job = await get_job_intelligence(db, current_user.id, job_intelligence_id)
    if row is None or job is None:
        raise HTTPException(status_code=404, detail=_VERSION_NOT_FOUND)

    document = document_of(row)
    make, media_type = _FORMATS[file_format]
    try:
        content = await asyncio.to_thread(make, document)  # off the event loop: it's CPU work
    except UnsupportedCharacters as e:
        raise HTTPException(status_code=422, detail=str(e))
    name = file_name(document, job.company or job.role, version, file_format)
    return Response(
        content=content, media_type=media_type,
        headers={"Content-Disposition": _content_disposition(name, "attachment"), "Cache-Control": "no-store"},
    )
