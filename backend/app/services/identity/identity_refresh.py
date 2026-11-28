"""Keeps the Engineering Identity up to date after the user's data changes
(a resume upload or analysis, a sync, a LinkedIn import, a project link, a
skill-gap analysis).

The refresh calls the model, so it runs as a background job: the request that
changed the data doesn't wait for it, and a failed refresh never fails that
request.

Only one refresh per user runs at a time. Changes made while one is running are
picked up by a single further refresh, however many there were.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.locks import advisory_lock
from app.schemas.identity.engineering_identity import EngineeringIdentityReport
from app.services.background import jobs
from app.services.identity.identity_synthesizer import (
    generate_engineering_identity,
    get_latest_engineering_identity,
)

logger = logging.getLogger(__name__)


async def refresh_identity(
    db: AsyncSession, user_id, *, source_event: str, requested_at: datetime,
) -> EngineeringIdentityReport:
    """Returns an identity that includes everything known at `requested_at`,
    waiting for any refresh already running for this user. A snapshot started
    since then already includes it all, so no new one is generated.
    """
    async with advisory_lock(jobs.session_factory, f"identity-refresh:{user_id}"):
        latest = await get_latest_engineering_identity(db, user_id)
        if latest is not None and latest.generated_at >= requested_at:
            return latest
        return await generate_engineering_identity(db, user_id, source_event=source_event)


async def trigger_identity_refresh(user_id, source_event: str) -> None:
    """Starts a refresh in the background. Call it once the change is committed."""
    requested_at = datetime.now(timezone.utc)

    async def work(job_db: AsyncSession):
        await refresh_identity(job_db, user_id, source_event=source_event, requested_at=requested_at)

    try:
        # Every change gets its own job: joining a running one would miss it.
        await jobs.start(user_id, "identity_auto_refresh", work, inputs=(uuid.uuid4(),))
    except Exception as e:
        logger.warning("Could not start an identity refresh after '%s': %s", source_event, e)
