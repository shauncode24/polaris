# backend/app/api/github.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.models.inference import GithubPortfolioReview, ProfileSnapshot
from app.services.github.github_reviewer import generate_github_portfolio_review

router = APIRouter(prefix="/github", tags=["github"])


async def _get_latest_portfolio_review(db: AsyncSession, user_id) -> dict | None:
    result = await db.execute(
        select(GithubPortfolioReview)
        .where(GithubPortfolioReview.user_id == user_id)
        .order_by(GithubPortfolioReview.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row.review_json if row else None


@router.get("/workspace")
async def get_github_workspace(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Read-only reconstruction of the last GitHub sync, so the GitHub
    page has real data to render on load without forcing a re-sync every
    visit. Same pattern as /resume/workspace — reads the latest inference
    snapshot rather than recomputing anything. Also includes the latest
    LLM portfolio review, if one has been generated.
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
    portfolio_review = await _get_latest_portfolio_review(db, current_user.id)

    return {
        "has_data": True,
        "username": payload.get("username") or current_user.github_username,
        "synced_at": snapshot.taken_at.isoformat(),
        "summary": payload.get("summary", {}),
        "repositories": payload.get("repositories", []),
        "insights": payload.get("insights", {}),
        "portfolio_review": portfolio_review,
    }


@router.post("/review")
async def run_github_portfolio_review(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Runs the LLM career-analysis layer on top of the deterministic
    GitHub analysis. Requires a completed GitHub sync first — this never
    calls the GitHub API itself, it only reasons over facts code has
    already extracted and verified (see github_knowledge.py).
    """
    try:
        report = await generate_github_portfolio_review(db, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return report