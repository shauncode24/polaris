"""Slow work answers 202 with a job id; the page then asks here until the job
has succeeded or failed.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.services.background import jobs

router = APIRouter(prefix="/background-jobs", tags=["background-jobs"])


class BackgroundJobStatus(BaseModel):
    id: str
    kind: str
    status: str  # "running" | "succeeded" | "failed"
    result: Any = None  # the response body, once succeeded
    error_status: int | None = None  # the HTTP status the failure stands for
    error_detail: Any = None
    created_at: datetime
    finished_at: datetime | None = None


async def run_in_background(user_id, kind: str, work: jobs.Work, *, inputs: tuple = ()) -> JSONResponse:
    """What a route returns for slow work. See `jobs.start`."""
    job_id = await jobs.start(user_id, kind, work, inputs=inputs)
    return JSONResponse(status_code=202, content={"job_id": str(job_id), "status": "running"})


@router.get("/{background_job_id}", response_model=BackgroundJobStatus)
async def get_background_job(
    background_job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await jobs.get(db, current_user.id, background_job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Background job not found")
    return BackgroundJobStatus(
        id=str(job.id), kind=job.kind, status=job.status, result=job.result_json,
        error_status=job.error_status, error_detail=job.error_json,
        created_at=job.created_at, finished_at=job.finished_at,
    )
