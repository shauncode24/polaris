"""Runs slow work, mostly model calls, after the request that asked for it has
been answered.

Work runs as a task inside the server process; its state lives in the
`background_jobs` table, so any process can report on it. While a job runs it
touches `heartbeat_at`. If the server stops partway, the heartbeat stops and
the next status check reports the job as failed.

A `work` function receives its own database session (the request's is closed by
then) and returns the response body. To fail with a particular status and
message it raises `HTTPException`, as a route would.
"""
import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import llm_budget
from app.core.database import AsyncSessionLocal
from app.core.llm import LLMError, require_ai_access
from app.core.rate_limit import require_ai_slot
from app.models.background import JOB_FAILED, JOB_RUNNING, JOB_SUCCEEDED, BackgroundJob

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 10
# A running job whose heartbeat is older than this is dead.
STALE_AFTER_SECONDS = 60
MAX_RUN_SECONDS = 15 * 60
# Finished jobs are only needed until the waiting page has read them.
KEEP_FINISHED_FOR = timedelta(days=1)

INTERRUPTED_MESSAGE = "The server stopped before this finished. Try again."
TOO_SLOW_MESSAGE = "This took too long and was stopped. Try again."
FAILED_MESSAGE = "Something went wrong while processing this. Try again."

Work = Callable[[AsyncSession], Awaitable[Any]]

# Tests point this at their own database engine.
session_factory = AsyncSessionLocal

# Held so that running tasks aren't garbage collected.
_tasks: set[asyncio.Task] = set()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dedupe_key(kind: str, inputs: tuple) -> str:
    digest = hashlib.sha256(json.dumps(inputs, default=str).encode()).hexdigest()[:32]
    return f"{kind}:{digest}"


def _failure(status: int, detail) -> dict:
    return {"status": JOB_FAILED, "error_status": status, "error_json": jsonable_encoder(detail)}


async def _fail_if_stale(db: AsyncSession, *conditions) -> None:
    now = _now()
    await db.execute(
        update(BackgroundJob)
        .where(
            *conditions,
            BackgroundJob.status == JOB_RUNNING,
            BackgroundJob.heartbeat_at < now - timedelta(seconds=STALE_AFTER_SECONDS),
        )
        .values(**_failure(500, INTERRUPTED_MESSAGE), finished_at=now)
    )


async def start(
    user_id, kind: str, work: Work, *, inputs: tuple = (), needs_model: bool = True,
    user_asked: bool = True,
) -> uuid.UUID:
    """Starts `work` and returns the job's id. If the same kind of work with
    the same `inputs` is already running for this user, returns that job
    instead, so a double click or a reloaded page doesn't pay for it twice.

    Work that `needs_model` isn't started for a user who couldn't call it:
    `LLMNotAllowedError` is raised. Work the user asked for counts against
    how much they may start in a short time: past that, `TooMuchWork` is raised.
    Joining a running job is neither refused nor counted.
    """
    key = _dedupe_key(kind, inputs)
    mine = (BackgroundJob.user_id == user_id, BackgroundJob.dedupe_key == key)

    counted = False
    async with session_factory() as db:
        await db.execute(delete(BackgroundJob).where(
            BackgroundJob.user_id == user_id,
            BackgroundJob.status != JOB_RUNNING,
            BackgroundJob.created_at < _now() - KEEP_FINISHED_FOR,
        ))
        await _fail_if_stale(db, *mine)

        # More than one pass only if the other job finishes between the two queries.
        for _ in range(3):
            running = await db.scalar(
                select(BackgroundJob.id).where(*mine, BackgroundJob.status == JOB_RUNNING)
            )
            if running is not None:
                await db.commit()
                return running
            if needs_model:
                await require_ai_access(user_id)
            if user_asked and not counted:
                require_ai_slot(user_id)
                counted = True

            now = _now()
            created = await db.scalar(
                insert(BackgroundJob)
                .values(
                    id=uuid.uuid4(), user_id=user_id, kind=kind, dedupe_key=key,
                    status=JOB_RUNNING, created_at=now, heartbeat_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=["user_id", "dedupe_key"], index_where=text("status = 'running'"),
                )
                .returning(BackgroundJob.id)
            )
            if created is not None:
                await db.commit()
                task = asyncio.create_task(_run(created, user_id, kind, work))
                _tasks.add(task)
                task.add_done_callback(_tasks.discard)
                return created

    raise RuntimeError(f"could not start a '{kind}' background job")


async def get(db: AsyncSession, user_id, job_id) -> BackgroundJob | None:
    """The user's job, or None. A job whose server stopped is marked failed here."""
    mine = (BackgroundJob.id == job_id, BackgroundJob.user_id == user_id)
    await _fail_if_stale(db, *mine)
    await db.commit()
    return await db.scalar(
        select(BackgroundJob).where(*mine).execution_options(populate_existing=True)
    )


async def _keep_alive(job_id) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        try:
            async with session_factory() as db:
                await db.execute(
                    update(BackgroundJob).where(BackgroundJob.id == job_id).values(heartbeat_at=_now())
                )
                await db.commit()
        except Exception as e:
            logger.warning("background job %s: heartbeat failed: %s", job_id, e)


async def _record(job_id, outcome: dict) -> None:
    async with session_factory() as db:
        # Only a job still marked running: one already reported as failed stays failed.
        await db.execute(
            update(BackgroundJob)
            .where(BackgroundJob.id == job_id, BackgroundJob.status == JOB_RUNNING)
            .values(**outcome, finished_at=_now())
        )
        await db.commit()


async def _run(job_id, user_id, kind: str, work: Work) -> None:
    llm_budget.current_user.set(user_id)  # this task's model calls are theirs
    heartbeat = asyncio.create_task(_keep_alive(job_id))
    started = time.monotonic()
    try:
        try:
            async with session_factory() as db:
                result = await asyncio.wait_for(work(db), MAX_RUN_SECONDS)
                outcome = {"status": JOB_SUCCEEDED, "result_json": jsonable_encoder(result)}
        except HTTPException as e:
            outcome = _failure(e.status_code, e.detail)
        except LLMError as e:
            outcome = _failure(e.status_code, str(e))
        except TimeoutError:
            logger.error("background job %s (%s) exceeded %ss", job_id, kind, MAX_RUN_SECONDS)
            outcome = _failure(504, TOO_SLOW_MESSAGE)
        except Exception:
            logger.exception("background job %s (%s) failed", job_id, kind)
            outcome = _failure(500, FAILED_MESSAGE)

        try:
            await _record(job_id, outcome)
        except Exception:
            logger.exception("background job %s (%s): could not save its outcome", job_id, kind)
            await _record(job_id, _failure(500, FAILED_MESSAGE))

        logger.info(
            "background job %s kind=%s status=%s duration_ms=%d",
            job_id, kind, outcome["status"], (time.monotonic() - started) * 1000,
        )
    finally:
        heartbeat.cancel()
