from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
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
from app.services.leetcode.leetcode_knowledge import build_leetcode_knowledge_object

from app.models.inference import ProfileSnapshot, LeetcodePortfolioReview

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


@router.get("/leetcode/workspace")
async def get_leetcode_workspace(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore LeetCode workspace sync snapshot & portfolio review from
    database, plus the on-the-fly cross-module inferences (Engineering
    Maturity Quadrant, company readiness, resume-claim check) that
    require both LeetCode and GitHub/Resume data together — these are
    intentionally computed live rather than persisted, since either
    source syncing again should shift them immediately.
    """
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

    knowledge = await build_leetcode_knowledge_object(db, current_user.id)

    return {
        "has_data": True,
        "username": current_user.leetcode_username,
        "synced_at": snapshot.taken_at.isoformat(),
        "summary": payload.get("stats", {}),
        "insights": payload.get("insights", {}),
        "portfolio_review": portfolio_review,
        "engineering_quadrant": knowledge.get("engineering_quadrant") if knowledge else None,
        "company_readiness": knowledge.get("company_readiness") if knowledge else None,
        "resume_claims": knowledge.get("resume_claims") if knowledge else None,
    }


@router.post("/leetcode/review")
async def run_leetcode_portfolio_review(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an LLM-powered review of the user's LeetCode performance."""
    from fastapi import HTTPException
    from app.services.leetcode.leetcode_reviewer import generate_leetcode_portfolio_review

    try:
        report = await generate_leetcode_portfolio_review(db, current_user.id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))