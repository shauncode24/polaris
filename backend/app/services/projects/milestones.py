from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inference import ProfileSnapshot
from app.schemas.projects import MilestoneItem

_LABELS = {
    "resume upload": "Resume uploaded",
    "github sync": "GitHub sync completed",
    "leetcode sync": "LeetCode sync completed",
    "leetcode manual submission": "LeetCode counts added manually",
}


async def build_recent_milestones(db: AsyncSession, user_id, limit: int = 5) -> list[MilestoneItem]:
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        MilestoneItem(
            label=_LABELS.get(row.note, (row.note or "Profile updated").capitalize()),
            occurred_at=row.taken_at,
        )
        for row in rows
    ]