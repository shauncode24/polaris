"""Slow work answers 202 with a job id, finishes after the response, and can
always be asked how it went. Real database; only the slow work is stubbed.
"""
import asyncio
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.llm import LLMUnavailableError
from app.models.background import BackgroundJob
from app.models.facts import Project, User
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import CareerPlan
from app.services.background import jobs
from tests.api.test_evidence import auth, run
from tests.api.test_job_library import add_goal, add_job, new_user

REVIEW = "/github/review"


class SlowWork:
    """Stands in for a service: waits until released, then returns or raises."""

    def __init__(self, outcome=None):
        self.outcome = {"headline": "done"} if outcome is None else outcome
        self.released = threading.Event()
        self.calls = 0

    async def __call__(self, *args, **kwargs):
        self.calls += 1
        while not self.released.is_set():
            await asyncio.sleep(0.01)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def work(monkeypatch):
    slow = SlowWork()
    monkeypatch.setattr("app.api.github.generate_github_portfolio_review", slow)
    yield slow
    slow.released.set()


def start(client, user, method="POST", path=REVIEW, **kwargs) -> str:
    response = client.start(method, path, headers=auth(user.id), **kwargs)
    assert response.status_code == 202, response.text[:300]
    assert response.json()["status"] == "running"
    return response.json()["job_id"]


def status(client, user, job_id) -> dict:
    response = client.get(f"/background-jobs/{job_id}", headers=auth(user.id))
    assert response.status_code == 200, response.text[:300]
    return response.json()


def finished(client, user, job_id) -> dict:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        job = status(client, user, job_id)
        if job["status"] != "running":
            return job
        time.sleep(0.02)
    raise AssertionError("the job did not finish")


def add_row(user, **values) -> str:
    async def go(db):
        now = datetime.now(timezone.utc)
        row = BackgroundJob(**{
            "user_id": user.id, "kind": "github_review", "dedupe_key": uuid.uuid4().hex,
            "status": "running", "created_at": now, "heartbeat_at": now, **values,
        })
        db.add(row)
        await db.commit()
        return str(row.id)
    return run(go)


def job_ids(user) -> set[str]:
    async def go(db):
        result = await db.execute(select(BackgroundJob.id).where(BackgroundJob.user_id == user.id))
        return {str(i) for i in result.scalars().all()}
    return run(go)


def test_the_request_is_answered_before_the_work_is_done(client, seeded, work):
    user = new_user()
    job_id = start(client, user)

    running = status(client, user, job_id)
    assert (running["status"], running["result"], running["finished_at"]) == ("running", None, None)

    work.released.set()
    done = finished(client, user, job_id)
    assert (done["status"], done["result"]) == ("succeeded", {"headline": "done"})
    assert done["kind"] == "github_review" and done["finished_at"] and done["error_detail"] is None


def test_asking_again_while_it_runs_joins_the_same_job(client, seeded, work):
    user, other = new_user(), new_user()
    first = start(client, user)

    assert start(client, user) == first
    assert start(client, other) != first  # another user's identical request is separate work

    work.released.set()
    finished(client, user, first)
    again = start(client, user)  # once finished, asking again does the work again
    assert again != first
    finished(client, user, again)
    assert work.calls == 3


def test_requests_for_different_things_get_their_own_jobs(client, seeded, monkeypatch):
    slow = SlowWork()
    monkeypatch.setattr("app.api.projects.generate_project_intelligence", slow)
    user = new_user()

    async def project_id(db):
        return await db.scalar(select(Project.id).where(Project.user_id == user.id))
    path = f"/projects/{run(project_id)}/intelligence"

    first = start(client, user, "GET", path, params={"framing": "one"})
    second = start(client, user, "GET", path, params={"framing": "two"})
    assert first != second
    slow.released.set()


@pytest.mark.parametrize("error, expected_status, expected_detail", [
    (HTTPException(status_code=400, detail="Sync GitHub first."), 400, "Sync GitHub first."),
    (HTTPException(status_code=502, detail={"error_type": "x", "message": "m"}), 502,
     {"error_type": "x", "message": "m"}),
    (ValueError("Sync GitHub first."), 400, "Sync GitHub first."),  # the route's own mapping
    (LLMUnavailableError("The AI service is busy."), 503, "The AI service is busy."),
    (RuntimeError("password=hunter2 at db.internal"), 500, jobs.FAILED_MESSAGE),
])
def test_a_failure_keeps_a_status_and_a_message_safe_to_show(
    client, seeded, work, error, expected_status, expected_detail,
):
    work.outcome = error
    work.released.set()
    user = new_user()

    job = finished(client, user, start(client, user))

    assert (job["status"], job["error_status"], job["error_detail"]) == ("failed", expected_status, expected_detail)
    assert job["result"] is None


def test_work_that_runs_too_long_is_stopped(client, seeded, work, monkeypatch):
    monkeypatch.setattr(jobs, "MAX_RUN_SECONDS", 0.1)
    user = new_user()

    job = finished(client, user, start(client, user))

    assert (job["error_status"], job["error_detail"]) == (504, jobs.TOO_SLOW_MESSAGE)


def test_a_long_job_stays_alive_while_its_server_is(client, seeded, work, monkeypatch):
    monkeypatch.setattr(jobs, "HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(jobs, "STALE_AFTER_SECONDS", 0.6)
    user = new_user()
    job_id = start(client, user)

    time.sleep(1.2)  # twice as long as a silent job would survive
    assert status(client, user, job_id)["status"] == "running"

    work.released.set()
    assert finished(client, user, job_id)["status"] == "succeeded"


def test_a_job_whose_server_stopped_is_reported_as_failed(client, seeded):
    user = new_user()
    silent = datetime.now(timezone.utc) - timedelta(seconds=jobs.STALE_AFTER_SECONDS + 5)
    dead = add_row(user, heartbeat_at=silent)
    alive = add_row(user)

    job = status(client, user, dead)

    assert (job["status"], job["error_status"], job["error_detail"]) == ("failed", 500, jobs.INTERRUPTED_MESSAGE)
    assert job["finished_at"]
    assert status(client, user, alive)["status"] == "running"


def test_a_dead_job_does_not_block_trying_again(client, seeded, work):
    user = new_user()
    work.released.set()
    first = start(client, user)
    finished(client, user, first)

    async def leave_it_running_and_silent(db):
        row = await db.get(BackgroundJob, uuid.UUID(first))
        row.status = "running"
        row.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=jobs.STALE_AFTER_SECONDS + 5)
        await db.commit()
    run(leave_it_running_and_silent)

    second = start(client, user)

    assert second != first
    assert finished(client, user, second)["status"] == "succeeded"


def test_old_finished_jobs_are_cleared_when_a_new_one_starts(client, seeded, work):
    user, other = new_user(), new_user()
    old = datetime.now(timezone.utc) - jobs.KEEP_FINISHED_FOR - timedelta(hours=1)
    old_finished = add_row(user, status="succeeded", created_at=old)
    recent = add_row(user, status="failed")
    old_running = add_row(user, created_at=old)
    someone_elses = add_row(other, status="succeeded", created_at=old)

    work.released.set()
    new = start(client, user)

    assert job_ids(user) == {recent, old_running, new}
    assert old_finished not in job_ids(user)
    assert job_ids(other) == {someone_elses}


def test_a_stored_comparison_is_answered_without_a_job(client, seeded, monkeypatch):
    async def nothing(*args, **kwargs):
        return None
    monkeypatch.setattr("app.api.jobs.trigger_identity_refresh", nothing)
    user = new_user()
    path = f"/jobs/by-intelligence/{add_job(user, 'Backend Engineer', ['python'])}"

    start(client, user, "GET", path)
    first = client.get(path, headers=auth(user.id))  # joins or follows the job above
    again = client.start("GET", path, headers=auth(user.id))

    assert first.status_code == 200
    assert again.status_code == 200 and again.json()["report"] == first.json()["report"]
    assert client.start("GET", path, headers=auth(user.id), params={"regenerate": True}).status_code == 202


# --- every converted route runs its work ------------------------------------

@pytest.fixture(scope="module")
def worker(seeded):
    """A user with enough data for each slow route to reach its work."""
    user = new_user()
    job = add_job(user, "Backend Engineer", ["python"])
    goal = add_goal(user, "Backend", job)

    async def link_repo(db):
        project = await db.scalar(select(Project).where(Project.user_id == user.id))
        project.github_repo_name = "ledger"
        db.add(GithubProjectAnalysis(
            user_id=user.id, repo_name="ledger", category="Backend", technologies=["python"],
            capabilities=[], computed_at=datetime.now(timezone.utc),
        ))
        await db.commit()
        return project.id
    user.project_id, user.job_id, user.goal_id = run(link_repo), job, goal
    return user


@pytest.mark.parametrize("method, path, body", [
    ("POST", "/goals/{goal}/plan", None),
    ("POST", "/job-intelligence/analyze", {"raw_text": "Backend Engineer. Python required."}),
    ("GET", "/jobs/by-intelligence/{job}?regenerate=true", None),
    ("POST", "/interview/ask", {"question": "Tell me about yourself"}),
    ("POST", "/resume/review", None),
    ("POST", "/resume/analyze?job_intelligence_id={job}", None),
    ("GET", "/resume/coherence?regenerate=true", None),
    ("POST", "/github/review", None),
    ("POST", "/sync/leetcode/review", None),
    ("POST", "/linkedin/ingest", {"raw_text": "Engineer at Acme"}),
    ("GET", "/projects/portfolio-narrative?regenerate=true", None),
    ("GET", "/projects/{project}/claim-audit?regenerate=true", None),
    ("GET", "/projects/{project}/intelligence", None),
    ("GET", "/projects/{project}/interview-questions?regenerate=true", None),
    ("POST", "/identity/refresh", None),
    ("POST", "/identity/weekly-brief/refresh", None),
])
def test_every_slow_route_runs_its_work_as_a_job(client, worker, method, path, body):
    """With no model reachable a job may use a fallback or fail saying so, but
    must never break.
    """
    path = path.format(goal=worker.goal_id, job=worker.job_id, project=worker.project_id)
    job_id = start(client, worker, method, path, json=body)

    job = finished(client, worker, job_id)

    assert job["error_detail"] != jobs.FAILED_MESSAGE
    assert job["status"] == "succeeded" or job["error_status"] in (400, 502, 503), job


def test_a_plan_built_in_the_background_is_saved(client, worker):
    plan = client.post(f"/goals/{worker.goal_id}/plan", headers=auth(worker.id))

    assert plan.status_code == 200, plan.text[:300]

    async def saved(db):
        return await db.get(CareerPlan, uuid.UUID(plan.json()["plan_id"]))
    assert run(saved).goal_id == worker.goal_id


@pytest.mark.parametrize("target, path, kwargs", [
    ("app.api.resume.ingest_resume", "/resume/upload",
     {"files": {"file": ("cv.pdf", b"%PDF-1.4 stub", "application/pdf")}}),
    ("app.api.linkedin.ingest_linkedin_profile", "/linkedin/ingest", {"json": {"raw_text": "x"}}),
    ("app.api.sync.sync_github", "/sync/github", {"json": {"username": "ivy", "token": "t"}}),
])
def test_work_gets_the_user_from_its_own_session(client, seeded, monkeypatch, target, path, kwargs):
    seen = {}

    async def text(raw_bytes):
        return "resume text"

    async def fake(*args, **kw):
        db, user = (args[1], args[2]) if "resume" in target else (args[0], args[1])
        seen["id"], seen["attached"] = user.id, user in db
        assert isinstance(user, User)
        raise HTTPException(status_code=400, detail="stop here")

    monkeypatch.setattr("app.api.resume.extract_text_from_pdf_bytes", text)
    monkeypatch.setattr(target, fake)
    user = new_user()

    response = client.post(path, headers=auth(user.id), **kwargs)

    assert response.json() == {"detail": "stop here"}
    assert seen == {"id": user.id, "attached": True}
