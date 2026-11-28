from fastapi import APIRouter, Depends, HTTPException
import logging
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.background_jobs import run_in_background
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import require_ai_slot
from app.core.security import decrypt_secret, encrypt_secret
from app.models.facts import User
from app.schemas.leetcode.leetcode_sync import LeetCodeManualSubmission
from app.schemas.shared.sync import GithubSyncRequest, LeetcodeSyncRequest
from app.services.github.github_client import GithubSyncError
from app.services.github.github_sync import sync_github
from app.services.leetcode.leetcode_client import LeetCodeSyncError
from app.services.leetcode.leetcode_sync import sync_leetcode, sync_leetcode_manual
from app.services.leetcode.engineering_snapshot import (
    persist_engineering_snapshot,
    get_latest_engineering_snapshot,
    get_engineering_snapshot_history,
    compute_engineering_snapshot,
)
from app.services.evidence.state import touch_evidence
from app.services.identity.identity_refresh import trigger_identity_refresh
from app.services.projects.reconcile import reconcile_projects

from app.models.inference import ProfileSnapshot, LeetcodePortfolioReview

router = APIRouter(prefix="/sync", tags=["sync"])
logger = logging.getLogger(__name__)


@router.post("/github")
async def trigger_github_sync(
    payload: GithubSyncRequest = GithubSyncRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    username = payload.username or current_user.github_username
    # SECURITY FIX (Phase 1 §1.4): current_user.github_token is now
    # stored ENCRYPTED at rest (see below) — it must be decrypted before
    # use. A token supplied directly in this request's payload is
    # already plaintext and is used as-is.
    token = payload.token or decrypt_secret(current_user.github_token)

    if not username or not token:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "reason": "GitHub username and personal access token are required."},
        )

    current_user.github_username = username
    # SECURITY FIX (Phase 1 §1.4): previously stored in plaintext. Only
    # the encrypted form is ever persisted; the plaintext `token` local
    # variable is used for the actual GitHub API calls below and never
    # written to the database.
    current_user.github_token = encrypt_secret(token)
    await db.commit()

    user_id = current_user.id

    # The token stays in memory: it is never written to the jobs table.
    async def work(job_db: AsyncSession):
        user = await job_db.get(User, user_id)
        try:
            result = await sync_github(job_db, user, username, token)
        except GithubSyncError as e:
            raise HTTPException(status_code=502, detail=str(e))

        await reconcile_projects(job_db, user_id)
        await touch_evidence(job_db, user_id)
        await persist_engineering_snapshot(job_db, user_id, "github sync")
        # Freshness fix — same trigger point as the proven
        # LeetcodeEngineeringSnapshot pattern above.
        await trigger_identity_refresh(user_id, "github sync")
        return result

    # The sync is worth doing without the model: what it can't do now waits.
    return await run_in_background(user_id, "github_sync", work, inputs=(username,), needs_model=False)


@router.post("/leetcode")
async def trigger_leetcode_sync(
    payload: LeetcodeSyncRequest = LeetcodeSyncRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    username = payload.username or current_user.leetcode_username
    if not username:
        return JSONResponse(status_code=400, content={"status": "error", "reason": "LeetCode username is required."})

    require_ai_slot(current_user.id)  # topic names not seen before go to the model
    current_user.leetcode_username = username
    await db.commit()

    try:
        result = await sync_leetcode(db, current_user, username)
    except LeetCodeSyncError as e:
        logger.warning("LeetCode sync degraded: %s", e)
        return JSONResponse(
            status_code=200,
            content={"status": "degraded", "reason": str(e), "fallback_form_required": True},
        )

    await touch_evidence(db, current_user.id)
    await persist_engineering_snapshot(db, current_user.id, "leetcode sync")
    await trigger_identity_refresh(current_user.id, "leetcode sync")

    return result


@router.post("/leetcode/manual")
async def submit_leetcode_manual(
    payload: LeetCodeManualSubmission,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_ai_slot(current_user.id)  # topic names not seen before go to the model
    result = await sync_leetcode_manual(db, current_user, payload.tag_counts)
    await touch_evidence(db, current_user.id)
    await persist_engineering_snapshot(db, current_user.id, "leetcode manual submission")
    await trigger_identity_refresh(current_user.id, "leetcode manual submission")
    return result


@router.get("/leetcode/workspace")
async def get_leetcode_workspace(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    snapshot = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == current_user.id)
        .where(ProfileSnapshot.note.in_(["leetcode sync", "leetcode manual submission"]))
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    snapshot = snapshot.scalar_one_or_none()
    if snapshot is None:
        return {"has_data": False}

    payload = snapshot.skills_json

    review_result = await db.execute(
        select(LeetcodePortfolioReview)
        .where(LeetcodePortfolioReview.user_id == current_user.id)
        .order_by(LeetcodePortfolioReview.created_at.desc())
        .limit(1)
    )
    review_row = review_result.scalar_one_or_none()
    portfolio_review = review_row.review_json if review_row else None

    latest_engineering = await get_latest_engineering_snapshot(db, current_user.id)
    if latest_engineering is None:
        live = await compute_engineering_snapshot(db, current_user.id)
        if live is not None:
            latest_engineering = {
                "leetcode_score": live["leetcode_score"],
                "github_score": live["github_score"],
                "quadrant_label": live["quadrant_label"],
                "description": live["description"],
                "company_readiness": live["company_readiness"],
                "resume_claims": live["resume_claims"],
            }

    engineering_history = await get_engineering_snapshot_history(db, current_user.id)

    return {
        "has_data": True,
        "username": current_user.leetcode_username,
        "synced_at": snapshot.taken_at.isoformat(),
        "summary": payload.get("stats", {}),
        "insights": payload.get("insights", {}),
        "portfolio_review": portfolio_review,
        "engineering_quadrant": (
            {
                "leetcode_score": latest_engineering["leetcode_score"],
                "github_score": latest_engineering["github_score"],
                "quadrant_label": latest_engineering["quadrant_label"],
                "description": latest_engineering["description"],
            }
            if latest_engineering else None
        ),
        "company_readiness": latest_engineering["company_readiness"] if latest_engineering else None,
        "resume_claims": latest_engineering["resume_claims"] if latest_engineering else None,
        "engineering_history": engineering_history,
    }


@router.post("/leetcode/review")
async def run_leetcode_portfolio_review(current_user: User = Depends(get_current_user)):
    from app.services.leetcode.leetcode_reviewer import generate_leetcode_portfolio_review

    user_id = current_user.id

    async def work(job_db: AsyncSession):
        try:
            return await generate_leetcode_portfolio_review(job_db, user_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return await run_in_background(user_id, "leetcode_review", work)
