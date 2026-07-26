from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.schemas.leetcode_sync import LeetCodeManualSubmission
from app.schemas.sync import GithubSyncRequest, LeetcodeSyncRequest
from app.services.github.github_client import GithubSyncError
from app.services.github.github_sync import sync_github
from app.services.leetcode.leetcode_client import LeetCodeSyncError
from app.services.leetcode.leetcode_sync import sync_leetcode, sync_leetcode_manual

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/github")
async def trigger_github_sync(
    payload: GithubSyncRequest = GithubSyncRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    username = payload.username or current_user.github_username
    token = payload.token or current_user.github_token

    if not username or not token:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "reason": "GitHub username and personal access token are required."},
        )

    # Save so the user doesn't have to retype the PAT on every future sync.
    current_user.github_username = username
    current_user.github_token = token
    await db.commit()

    try:
        return await sync_github(db, current_user, username, token)
    except GithubSyncError as e:
        return JSONResponse(status_code=502, content={"status": "error", "reason": str(e)})


@router.post("/leetcode")
async def trigger_leetcode_sync(
    payload: LeetcodeSyncRequest = LeetcodeSyncRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    username = payload.username or current_user.leetcode_username
    if not username:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "LeetCode username is required."})

    current_user.leetcode_username = username
    await db.commit()

    try:
        return await sync_leetcode(db, current_user, username)
    except LeetCodeSyncError as e:
        print(f"[TRACING] LeetCode sync degraded: {e}", flush=True)
        return JSONResponse(
            status_code=200,
            content={"status": "degraded", "reason": str(e), "fallback_form_required": True},
        )


@router.post("/leetcode/manual")
async def submit_leetcode_manual(
    payload: LeetCodeManualSubmission,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await sync_leetcode_manual(db, current_user, payload.tag_counts)