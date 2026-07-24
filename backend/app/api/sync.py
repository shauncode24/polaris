from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.database import get_db
from app.core.settings import settings
from app.schemas.leetcode_sync import LeetCodeManualSubmission
from app.services.github.github_client import GithubSyncError
from app.services.github.github_sync import sync_github
from app.services.leetcode.leetcode_client import LeetCodeSyncError
from app.services.leetcode.leetcode_sync import sync_leetcode, sync_leetcode_manual

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/github")
async def trigger_github_sync(db=Depends(get_db)):
    try:
        return await sync_github(db, settings.github_username, settings.github_token)
    except GithubSyncError as e:
        return JSONResponse(
            status_code=502,
            content={"status": "error", "reason": str(e)},
        )


@router.post("/leetcode")
async def trigger_leetcode_sync(db=Depends(get_db)):
    try:
        return await sync_leetcode(db, settings.leetcode_username)
    except LeetCodeSyncError as e:
        # Graceful degradation: this is an expected failure mode for an
        # unofficial endpoint, not a server error. 200 + a structured
        # "fallback_form_required" flag lets the client render the manual
        # form instead of surfacing a crash.
        print(f"[TRACING] LeetCode sync degraded: {e}", flush=True)
        return JSONResponse(
            status_code=200,
            content={
                "status": "degraded",
                "reason": str(e),
                "fallback_form_required": True,
            },
        )


@router.post("/leetcode/manual")
async def submit_leetcode_manual(payload: LeetCodeManualSubmission, db=Depends(get_db)):
    return await sync_leetcode_manual(db, payload.tag_counts)