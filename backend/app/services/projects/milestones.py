"""Real per-project timeline, replacing the old account-level sync-event
feed (which only ever told the user "GitHub sync completed" — nothing
about their PROJECTS specifically). Reads consecutive PortfolioAnalysis
rows (now actually written by github_sync.py — see the wiring change
there) and surfaces their real, dated observations. This is genuine
project-level memory instead of account-level noise wearing a project
page's costume.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_analysis import PortfolioAnalysis
from app.schemas.projects import MilestoneItem

MAX_SNAPSHOTS = 6


async def build_recent_milestones(db: AsyncSession, user_id, limit: int = 5) -> list[MilestoneItem]:
    result = await db.execute(
        select(PortfolioAnalysis)
        .where(PortfolioAnalysis.user_id == user_id)
        .order_by(PortfolioAnalysis.computed_at.desc())
        .limit(MAX_SNAPSHOTS)
    )
    snapshots = list(result.scalars().all())
    if not snapshots:
        return []

    milestones: list[MilestoneItem] = []
    for snapshot in snapshots:
        for obs in (snapshot.observations or [])[:3]:
            milestones.append(MilestoneItem(label=obs, occurred_at=snapshot.computed_at))
        if len(milestones) >= limit:
            break

    return milestones[:limit]