"""Each user may make only so many model calls a day. Real database; only the
model is stubbed.
"""
import asyncio
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from openai import RateLimitError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import llm, llm_budget
from app.core.llm import LLMBudgetError, LLMUnavailableError, Prompt, llm_json
from app.models.background import BackgroundJob
from app.models.facts import Experience, Project
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import EngineeringIdentity
from app.models.usage import LlmUsage
from tests.api.conftest import _new_engine
from tests.api.test_evidence import auth, run
from tests.api.test_job_library import add_job, new_user
from tests.llm_stub import api_error, model, reply  # noqa: F401 (model is a fixture)

MESSAGE = "You've reached today's limit of 3 AI requests. It resets at midnight UTC."
ANSWER = {"answer": "yes"}


@pytest.fixture(autouse=True)
def three_a_day(monkeypatch):
    monkeypatch.setattr(llm_budget, "DAILY_CALLS", 3)


@pytest.fixture
def quiet_refresh(monkeypatch):
    async def nothing(*args, **kwargs):
        return None
    for module in ("linkedin", "jobs", "sync"):
        monkeypatch.setattr(f"app.api.{module}.trigger_identity_refresh", nothing)


def used(user) -> int:
    async def go(db):
        return await db.scalar(select(LlmUsage.calls).where(
            LlmUsage.user_id == user.id, LlmUsage.day == datetime.now(timezone.utc).date()))
    return run(go) or 0


def spend(user, calls: int, *, days_ago: int = 0):
    async def go(db):
        day = datetime.now(timezone.utc).date() - timedelta(days=days_ago)
        db.add(LlmUsage(user_id=user.id, day=day, calls=calls))
        await db.commit()
    run(go)


def on_behalf_of(user, make_calls):
    """Runs `make_calls()` as a request or job of `user` would."""
    async def go(_db):
        engine = _new_engine()
        real, llm_budget.session_factory = llm_budget.session_factory, async_sessionmaker(engine)
        token = llm_budget.current_user.set(user.id)
        try:
            return await make_calls()
        finally:
            llm_budget.current_user.reset(token)
            llm_budget.session_factory = real
            await engine.dispose()
    return run(go)


def ask(**options):
    return llm_json(Prompt("system", "user"), dict, label="test", **options)


# --- counting ----------------------------------------------------------------

def test_calls_stop_at_the_daily_limit_even_where_there_is_a_fallback(seeded, model):
    user = new_user()
    model.will(ANSWER, ANSWER, ANSWER)

    async def calls():
        for _ in range(3):
            await ask()
        with pytest.raises(LLMBudgetError) as refused:
            await ask(fallback=lambda: {"made": "up"})
        return refused.value

    error = on_behalf_of(user, calls)

    assert (str(error), error.status_code) == (MESSAGE, 429)
    assert isinstance(error, LLMUnavailableError)  # so loops stop asking
    assert len(model.requests) == 3 and used(user) == 3


def test_each_user_and_each_day_is_counted_separately(seeded, model):
    spent, fresh = new_user(), new_user()
    spend(spent, 3)
    spend(fresh, 3, days_ago=1)
    model.will(ANSWER)

    assert on_behalf_of(fresh, ask).value == ANSWER
    with pytest.raises(LLMBudgetError):
        on_behalf_of(spent, ask)


def test_a_call_the_service_never_answered_is_not_counted(seeded, model):
    user = new_user()
    model.will(api_error(RateLimitError, 429))

    with pytest.raises(LLMUnavailableError):
        on_behalf_of(user, ask)

    assert used(user) == 0


def test_every_answered_attempt_is_counted(seeded, model):
    user = new_user()
    model.will(reply(ANSWER, finish_reason="length"), ANSWER)

    on_behalf_of(user, ask)

    assert used(user) == 2


def test_calls_made_at_the_same_moment_cannot_exceed_the_limit(seeded):
    user = new_user()

    async def all_at_once():
        return await asyncio.gather(*(llm_budget.reserve(user.id) for _ in range(12)))

    granted = on_behalf_of(user, all_at_once)

    assert sum(day is not None for day in granted) == 3 and used(user) == 3


def test_no_limit_can_be_configured(seeded, model, monkeypatch):
    monkeypatch.setattr(llm_budget, "DAILY_CALLS", 0)
    user = new_user()
    spend(user, 500)
    model.will(ANSWER)

    assert on_behalf_of(user, ask).value == ANSWER
    assert used(user) == 500


def test_calls_outside_a_request_or_job_are_not_limited(model):
    model.will(ANSWER)
    assert asyncio.run(ask()).value == ANSWER


# --- through the app ---------------------------------------------------------

def job_count(user) -> int:
    async def go(db):
        result = await db.execute(select(BackgroundJob.id).where(BackgroundJob.user_id == user.id))
        return len(result.all())
    return run(go)


def test_new_ai_work_is_refused_with_a_clear_message(client, seeded, model):
    user = new_user()
    spend(user, 3)

    for method, path, body in [
        ("POST", "/linkedin/ingest", {"raw_text": "Engineer at Acme"}),
        ("POST", "/interview/ask", {"question": "Tell me about yourself"}),
        ("POST", "/identity/refresh", None),
    ]:
        response = client.start(method, path, headers=auth(user.id), json=body)
        assert (response.status_code, response.json()) == (429, {"detail": MESSAGE}), path

    assert job_count(user) == 0 and model.requests == []


def test_a_job_already_running_can_still_be_followed_at_the_limit(client, seeded, monkeypatch):
    release = threading.Event()

    async def slow(*args, **kwargs):
        while not release.is_set():
            await asyncio.sleep(0.01)
        return {"headline": "done"}
    monkeypatch.setattr("app.api.github.generate_github_portfolio_review", slow)
    user = new_user()
    started = client.start("POST", "/github/review", headers=auth(user.id))
    run_out(user)

    try:
        reloaded = client.start("POST", "/github/review", headers=auth(user.id))
        assert reloaded.status_code == 202 and reloaded.json() == started.json()
    finally:
        release.set()


def test_yesterdays_calls_do_not_stop_todays_work(client, seeded, monkeypatch):
    async def review(*args, **kwargs):
        return {"headline": "done"}
    monkeypatch.setattr("app.api.github.generate_github_portfolio_review", review)
    user = new_user()
    spend(user, 3, days_ago=1)

    response = client.post("/github/review", headers=auth(user.id))

    assert response.status_code == 200, response.text[:300]


def test_saved_results_are_still_shown_at_the_limit(client, seeded, quiet_refresh):
    user = new_user()
    path = f"/jobs/by-intelligence/{add_job(user, 'Backend Engineer', ['python'])}"
    first = client.get(path, headers=auth(user.id))
    assert first.status_code == 200, first.text[:300]
    run_out(user)

    again = client.get(path, headers=auth(user.id))

    assert again.status_code == 200 and again.json()["report"] == first.json()["report"]


def run_out(user):
    async def go(db):
        row = await db.get(LlmUsage, (user.id, datetime.now(timezone.utc).date()))
        if row is None:
            db.add(LlmUsage(user_id=user.id, day=datetime.now(timezone.utc).date(), calls=3))
        else:
            row.calls = 3
        await db.commit()
    run(go)


def test_calls_made_by_a_background_job_count_against_its_user(client, seeded, model, quiet_refresh):
    user = new_user()
    cut_off = reply({}, finish_reason="length")
    model.will(cut_off, cut_off)

    client.post("/linkedin/ingest", headers=auth(user.id), json={"raw_text": "Engineer at Acme"})

    assert used(user) == 2


def test_a_job_that_uses_up_the_limit_fails_saying_so(client, seeded, model, quiet_refresh):
    user = new_user()
    spend(user, 2)
    model.will(reply({}, finish_reason="length"))  # the retry has no call left

    response = client.post("/linkedin/ingest", headers=auth(user.id), json={"raw_text": "Engineer at Acme"})

    assert MESSAGE in str(response.json()["detail"])
    assert len(model.requests) == 1


def test_calls_made_while_answering_a_request_are_counted(client, seeded, model, quiet_refresh):
    user = new_user()
    unseen = f"topic-{uuid.uuid4().hex[:12]}"
    model.will({"results": [{"raw": unseen, "canonical": "x", "is_valid_skill": False}]})

    client.post("/sync/leetcode/manual", headers=auth(user.id), json={"tag_counts": {unseen: 2}})

    assert used(user) == 1


def test_syncs_still_work_at_the_limit(client, seeded, model, monkeypatch):
    async def fake_sync(db, user, username, token):
        return {"status": "success"}
    monkeypatch.setattr("app.api.sync.sync_github", fake_sync)
    user = new_user()
    spend(user, 3)

    github = client.post("/sync/github", headers=auth(user.id), json={"username": "ivy", "token": "t"})
    leetcode = client.post("/sync/leetcode/manual", headers=auth(user.id),
                           json={"tag_counts": {f"topic-{uuid.uuid4().hex[:12]}": 2}})

    assert github.status_code == 200, github.text[:300]
    assert leetcode.status_code == 200, leetcode.text[:300]

    # Neither starts an identity refresh that could only fail or save filler.
    async def refreshed(db):
        jobs = await db.execute(select(BackgroundJob.kind).where(BackgroundJob.user_id == user.id))
        snapshots = await db.execute(select(EngineeringIdentity.id).where(EngineeringIdentity.user_id == user.id))
        return set(jobs.scalars().all()), snapshots.all()
    assert run(refreshed) == ({"github_sync"}, [])
    assert model.requests == []


@pytest.mark.parametrize("path", ["/resume/workspace", "/profile/data"])
def test_pages_still_load_at_the_limit(client, seeded, model, path):
    user = new_user()

    async def unclassified_skills(db):
        db.add(Experience(user_id=user.id, resume_id=user.resume_id, role="Engineer", company="Acme",
                          stack=[f"Tool{uuid.uuid4().hex[:10]}"]))
        project = await db.scalar(select(Project).where(Project.user_id == user.id))
        db.add(GithubProjectAnalysis(
            user_id=user.id, repo_name=project.name, category="Backend",
            technologies=[f"Tool{uuid.uuid4().hex[:10]}"], capabilities=[],
            computed_at=datetime.now(timezone.utc), repo_created_at=datetime.now(timezone.utc),
        ))
        await db.commit()
    run(unclassified_skills)
    spend(user, 3)

    response = client.get(path, headers=auth(user.id))

    assert response.status_code == 200, response.text[:300]
    assert model.requests == []
    if path == "/resume/workspace":
        assert MESSAGE in response.text
