"""Postgres advisory locks: one holder at a time, across every server process."""
import asyncio
import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# How often a waiter asks again.
RETRY_SECONDS = 1.0


def _lock_key(name: str) -> int:
    """Postgres identifies an advisory lock by a signed 64-bit number."""
    return int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "big", signed=True)


@asynccontextmanager
async def advisory_lock(session_factory: async_sessionmaker[AsyncSession], name: str) -> AsyncIterator[None]:
    """Holds the lock called `name` while the block runs, waiting for it first.

    The lock belongs to a transaction kept open on its own connection, so it is
    released when the block ends, and also if this server dies. (Unlike
    session-level locks, these work through a connection pooler.) Waiting holds
    no connection.
    """
    key = _lock_key(name)
    while True:
        async with session_factory() as db:
            if await db.scalar(select(func.pg_try_advisory_xact_lock(key))):
                # The transaction sits idle while the block works; the database
                # must not end it, and the lock with it, for that.
                await db.execute(text("SET LOCAL idle_in_transaction_session_timeout = 0"))
                yield
                return
        await asyncio.sleep(RETRY_SECONDS)
