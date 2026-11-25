"""When did this user's evidence last change?

Every event that changes what is known about a user (resume upload, GitHub
or LeetCode sync, LinkedIn import, a project link, a user edit) calls
`touch_evidence`. AI reports built from the evidence (tailored resume,
claim audit, interview questions, ...) are cached; a cached report older
than the user's `evidence_updated_at` was built from outdated evidence, so
its reader treats it as missing. Use `evidence_cutoff` to get the timestamp
to compare against.
"""
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import User


async def touch_evidence(db: AsyncSession, user_id) -> None:
    await db.execute(
        update(User).where(User.id == user_id).values(evidence_updated_at=datetime.now(timezone.utc))
    )
    await db.commit()


async def evidence_cutoff(db: AsyncSession, user_id) -> datetime | None:
    """Cached reports created before this are out of date. None means the
    evidence has never been touched, so every cached report is current.
    """
    result = await db.execute(select(User.evidence_updated_at).where(User.id == user_id))
    return result.scalar_one_or_none()
