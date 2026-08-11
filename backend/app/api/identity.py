from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.schemas.identity.engineering_identity import EngineeringIdentityReport, InvalidateIdentityRequest
from app.schemas.identity.weekly_brief import WeeklyBriefReport
from app.services.identity.identity_synthesizer import (
    generate_engineering_identity,
    get_engineering_identity_history,
    get_latest_engineering_identity,
    invalidate_engineering_identity,
)
from app.services.identity.weekly_brief import (
    InsufficientHistoryError,
    generate_weekly_brief,
    get_latest_weekly_brief,
)

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("", response_model=EngineeringIdentityReport)
async def get_engineering_identity(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    cached = await get_latest_engineering_identity(db, current_user.id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail="No Engineering Identity generated yet — call POST /identity/refresh first.",
        )
    return cached


@router.post("/refresh", response_model=EngineeringIdentityReport)
async def refresh_engineering_identity(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await generate_engineering_identity(db, current_user.id)


@router.get("/history", response_model=list[EngineeringIdentityReport])
async def get_identity_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Most-recent-first, INCLUDING invalidated snapshots — the audit
    trail for "why did Identity say X on a given day," and whether that
    snapshot has since been flagged as known-bad.
    """
    return await get_engineering_identity_history(db, current_user.id, limit=limit)


@router.post("/{identity_id}/invalidate", response_model=EngineeringIdentityReport)
async def invalidate_identity_snapshot(
    identity_id: UUID,
    payload: InvalidateIdentityRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Flags one specific past Engineering Identity snapshot as
    known-bad (e.g. a transient sync hiccup fed a wrong number into it).
    Does not delete the row or generate a new one — call POST
    /identity/refresh separately for a corrected snapshot.
    """
    report = await invalidate_engineering_identity(db, current_user.id, identity_id, payload.reason)
    if report is None:
        raise HTTPException(status_code=404, detail="Engineering Identity snapshot not found.")
    return report


@router.get("/weekly-brief", response_model=WeeklyBriefReport)
async def get_weekly_brief(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    cached = await get_latest_weekly_brief(db, current_user.id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail="No weekly brief generated yet — call POST /identity/weekly-brief/refresh first.",
        )
    return cached


@router.post("/weekly-brief/refresh", response_model=WeeklyBriefReport)
async def refresh_weekly_brief(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        return await generate_weekly_brief(db, current_user.id)
    except InsufficientHistoryError as e:
        raise HTTPException(status_code=400, detail=str(e))