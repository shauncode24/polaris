"""Freshness fix: EngineeringIdentity previously only ever updated when
a human explicitly called POST /identity/refresh — unlike
LeetcodeEngineeringSnapshot, which already proves the "auto-append on a
real sync/upload event" pattern works in this codebase (see
leetcode/engineering_snapshot.py's persist_engineering_snapshot, called
from api/sync.py after every GitHub/LeetCode sync). This module is that
same pattern applied to EngineeringIdentity, wired into the four real
data-producing pages: Resume (upload + analyze), GitHub (sync), LeetCode
(sync + manual submission), and Jobs (skill-gap analysis).

Failures here are swallowed (logged, not raised) — regenerating the
Engineering Identity is a best-effort side effect of these endpoints,
never a reason to fail the upload/sync/analysis itself. This mirrors
the graceful-degradation philosophy used everywhere else in this
codebase (LLM fails -> deterministic fallback; here, refresh fails ->
the endpoint's own real result is still returned untouched).
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.identity.identity_synthesizer import generate_engineering_identity

logger = logging.getLogger(__name__)


async def trigger_identity_refresh(db: AsyncSession, user_id, source_event: str) -> None:
    try:
        await generate_engineering_identity(db, user_id, source_event=source_event)
        logger.info("Engineering Identity auto-refreshed after '%s'", source_event)
    except Exception as e:
        logger.warning("Engineering Identity auto-refresh failed after '%s': %s", source_event, e)