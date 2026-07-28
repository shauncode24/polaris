# backend/app/api/github.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.models.inference import ProfileSnapshot

router = APIRouter(prefix="/github", tags=["github"])


@router.get("/workspace")
async def get_github_workspace(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Read-only reconstruction of the last GitHub sync, so the GitHub
    page has real data to render on load without forcing a re-sync every
    visit. Same pattern as /resume/workspace — reads the latest inference
    snapshot rather than recomputing anything.
    """
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == current_user.id)
        .where(ProfileSnapshot.note == "github sync")
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()

    if snapshot is None or not isinstance(snapshot.skills_json, dict):
        return {"has_data": False}

    payload = snapshot.skills_json
    return {
        "has_data": True,
        "username": payload.get("username") or current_user.github_username,
        "synced_at": snapshot.taken_at.isoformat(),
        "summary": payload.get("summary", {}),
        "repositories": payload.get("repositories", []),
        "insights": payload.get("insights", {}),
    }