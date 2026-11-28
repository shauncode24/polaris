"""The Engineering Identity is refreshed in the background, one refresh per
user at a time, without losing changes. Real database and lock; the model is
unreachable, so each snapshot uses the fallback text.
"""
import asyncio
import threading
import time
from collections import Counter

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import locks
from app.models.background import BackgroundJob
from app.models.inference import EngineeringIdentity
from app.services.identity import identity_synthesizer
from tests.api.conftest import _new_engine
from tests.api.test_evidence import auth, run
from tests.api.test_job_library import new_user

EVENT = "leetcode manual submission"


class Reading:
    """Wraps the first part of a refresh, so a test can hold one user's refresh
    there and see how many ran.
    """

    def __init__(self, real):
        self.real = real
        self.held: set = set()
        self.failures = 0
        self.started: Counter = Counter()
        self.active: Counter = Counter()
        self.most_at_once: Counter = Counter()

    async def __call__(self, db, user_id):
        self.started[user_id] += 1
        self.active[user_id] += 1
        self.most_at_once[user_id] = max(self.most_at_once[user_id], self.active[user_id])
        try:
            while user_id in self.held:
                await asyncio.sleep(0.01)
            if self.failures:
                self.failures -= 1
                raise RuntimeError("the database went away")
            return await self.real(db, user_id)
        finally:
            self.active[user_id] -= 1


@pytest.fixture
def reading(monkeypatch):
    monkeypatch.setattr(locks, "RETRY_SECONDS", 0.02)
    stand_in = Reading(identity_synthesizer.build_identity_facts)
    monkeypatch.setattr(identity_synthesizer, "build_identity_facts", stand_in)
    yield stand_in
    stand_in.held.clear()


def wait_until(condition, what: str):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting until {what}")


def change_data(client, user):
    response = client.post("/sync/leetcode/manual", headers=auth(user.id), json={"tag_counts": {"python": 5}})
    assert response.status_code == 200, response.text[:300]


def refreshes(user) -> list[str]:
    async def go(db):
        result = await db.execute(select(BackgroundJob.status).where(
            BackgroundJob.user_id == user.id, BackgroundJob.kind == "identity_auto_refresh",
        ))
        return list(result.scalars().all())
    return run(go)


def all_finished(user):
    wait_until(lambda: "running" not in refreshes(user), "the refreshes finished")


def snapshots(user) -> list[EngineeringIdentity]:
    async def go(db):
        result = await db.execute(select(EngineeringIdentity).where(
            EngineeringIdentity.user_id == user.id,
        ).order_by(EngineeringIdentity.created_at))
        return list(result.scalars().all())
    return run(go)


def test_a_change_is_saved_without_waiting_for_the_refresh(client, seeded, reading):
    user = new_user()
    reading.held.add(user.id)

    change_data(client, user)  # answers although the refresh can't finish

    wait_until(lambda: reading.started[user.id] == 1, "the refresh started")
    assert refreshes(user) == ["running"] and snapshots(user) == []

    reading.held.clear()
    all_finished(user)
    assert refreshes(user) == ["succeeded"]
    assert [s.source_event for s in snapshots(user)] == [EVENT]


def test_changes_during_a_refresh_get_exactly_one_more(client, seeded, reading):
    user = new_user()
    reading.held.add(user.id)
    change_data(client, user)
    wait_until(lambda: reading.started[user.id] == 1, "the refresh started")

    for _ in range(3):
        change_data(client, user)
    time.sleep(0.3)  # time for a second refresh to start, if it wrongly could
    assert reading.started[user.id] == 1

    reading.held.clear()
    all_finished(user)

    assert refreshes(user) == ["succeeded"] * 4
    assert reading.started[user.id] == 2
    assert reading.most_at_once[user.id] == 1
    assert len(snapshots(user)) == 2


def test_one_users_refresh_does_not_hold_up_anothers(client, seeded, reading):
    slow, other = new_user(), new_user()
    reading.held.add(slow.id)
    change_data(client, slow)
    wait_until(lambda: reading.started[slow.id] == 1, "the first refresh started")

    change_data(client, other)

    all_finished(other)
    assert len(snapshots(other)) == 1 and refreshes(slow) == ["running"]


def test_asking_for_a_refresh_waits_for_the_running_one_then_includes_the_latest(client, seeded, reading):
    user = new_user()
    reading.held.add(user.id)
    change_data(client, user)
    wait_until(lambda: reading.started[user.id] == 1, "the refresh started")

    job_id = client.start("POST", "/identity/refresh", headers=auth(user.id)).json()["job_id"]
    time.sleep(0.3)
    assert reading.started[user.id] == 1

    reading.held.clear()
    wait_until(
        lambda: client.get(f"/background-jobs/{job_id}", headers=auth(user.id)).json()["status"] != "running",
        "the requested refresh finished",
    )
    all_finished(user)

    job = client.get(f"/background-jobs/{job_id}", headers=auth(user.id)).json()
    assert job["status"] == "succeeded", job
    assert reading.started[user.id] == 2 and reading.most_at_once[user.id] == 1
    newest = snapshots(user)[-1]
    assert newest.source_event == "manual_refresh"


def test_a_failed_refresh_lets_the_next_one_run(client, seeded, reading):
    user = new_user()
    reading.failures = 1

    change_data(client, user)
    all_finished(user)
    assert refreshes(user) == ["failed"] and snapshots(user) == []

    change_data(client, user)
    all_finished(user)
    assert len(snapshots(user)) == 1


def test_a_refresh_waits_for_another_server_holding_the_lock(client, seeded, reading):
    user = new_user()
    taken, release = threading.Event(), threading.Event()

    async def another_server():
        engine = _new_engine()
        factory = async_sessionmaker(engine, class_=AsyncSession)
        async with locks.advisory_lock(factory, f"identity-refresh:{user.id}"):
            taken.set()
            while not release.is_set():
                await asyncio.sleep(0.01)
        await engine.dispose()

    holder = threading.Thread(target=asyncio.run, args=(another_server(),))
    holder.start()
    try:
        assert taken.wait(10)
        change_data(client, user)
        time.sleep(0.3)
        assert reading.started[user.id] == 0 and refreshes(user) == ["running"]
    finally:
        release.set()
        holder.join(10)

    all_finished(user)
    assert len(snapshots(user)) == 1


def test_a_refresh_that_cannot_start_does_not_fail_the_change(client, seeded, monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("no jobs today")
    monkeypatch.setattr("app.services.identity.identity_refresh.jobs.start", broken)

    change_data(client, new_user())
