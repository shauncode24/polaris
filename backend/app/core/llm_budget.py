"""How many model calls each user may make in a day.

The model account's quota is shared by everyone, so each user gets a daily
number of calls. Days are UTC days. A call is counted before it is sent, and
given back if the service never answered it.

`current_user` says whose calls are being made. It is set when a request is
authenticated and when a background job runs; calls made outside both (the
evaluation scripts) are not limited.
"""
import os
from contextvars import ContextVar
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.database import AsyncSessionLocal
from app.models.usage import LlmUsage

current_user: ContextVar = ContextVar("llm_budget_user", default=None)

# 0 or less means no limit. (.env is loaded by the database import above.)
DAILY_CALLS = int(os.environ.get("LLM_DAILY_CALLS_PER_USER") or 100)

# Tests point this at their own database engine.
session_factory = AsyncSessionLocal


def _today() -> date:
    return datetime.now(timezone.utc).date()


async def reserve(user_id) -> date | None:
    """Counts one call and returns the day it was counted on, or None if the
    user has none left today. Safe when many calls ask at once.
    """
    day = _today()
    statement = (
        insert(LlmUsage)
        .values(user_id=user_id, day=day, calls=1)
        .on_conflict_do_update(
            index_elements=["user_id", "day"],
            set_={"calls": LlmUsage.calls + 1},
            where=LlmUsage.calls < DAILY_CALLS,
        )
        .returning(LlmUsage.calls)
    )
    async with session_factory() as db:
        counted = await db.scalar(statement)
        await db.commit()
    return day if counted is not None else None


async def refund(user_id, day: date) -> None:
    async with session_factory() as db:
        await db.execute(
            update(LlmUsage)
            .where(LlmUsage.user_id == user_id, LlmUsage.day == day, LlmUsage.calls > 0)
            .values(calls=LlmUsage.calls - 1)
        )
        await db.commit()


async def has_calls_left(user_id) -> bool:
    if DAILY_CALLS <= 0:
        return True
    async with session_factory() as db:
        used = await db.scalar(
            select(LlmUsage.calls).where(LlmUsage.user_id == user_id, LlmUsage.day == _today())
        )
    return (used or 0) < DAILY_CALLS
