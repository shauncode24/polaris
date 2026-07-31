from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.schemas.engineering_identity import EngineeringIdentityReport
from app.schemas.weekly_brief import WeeklyBriefReport
from app.services.identity.identity_synthesizer import (
    generate_engineering_identity,
    get_latest_engineering_identity,
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