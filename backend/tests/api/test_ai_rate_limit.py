"""Each user may start only so much AI work in a short time. Real database; the
work itself is stood in for.
"""
import asyncio
import threading

import pytest

from app.core import llm_budget, rate_limit
from app.services.identity import identity_refresh
from tests.api.test_evidence import auth, run
from tests.api.test_job_library import add_job, new_user
from tests.api.test_llm_budget import job_count, spend
from tests.llm_stub import model  # noqa: F401 (a fixture)

REFUSED = "You've started a lot of AI work in a short time. Try again in "


@pytest.fixture(autouse=True)
def two_at_a_time(monkeypatch):
    monkeypatch.setattr(rate_limit.ai_work, "limit", 2)
    rate_limit.ai_work.clear()
    yield
    rate_limit.ai_work.clear()


@pytest.fixture
def reviews(monkeypatch):
    """GitHub reviews that finish at once."""
    async def review(*args, **kwargs):
        return {"headline": "done"}
    monkeypatch.setattr("app.api.github.generate_github_portfolio_review", review)


def start_review(client, user):
    return client.start("POST", "/github/review", headers=auth(user.id))


def use_up(client, user):
    for _ in range(2):
        assert client.post("/github/review", headers=auth(user.id)).status_code == 200


def assert_refused(response):
    assert response.status_code == 429, response.text
    assert response.json()["detail"].startswith(REFUSED)
    assert 1 <= int(response.headers["retry-after"]) <= 60


def test_work_past_the_limit_is_refused_before_it_starts(client, seeded, model, reviews):
    user = new_user()
    use_up(client, user)

    for method, path, body in [
        ("POST", "/github/review", None),
        ("POST", "/linkedin/ingest", {"raw_text": "Engineer at Acme"}),
        ("POST", "/interview/ask", {"question": "Tell me about yourself"}),
        # Takes no daily budget to start, but is AI work all the same.
        ("POST", "/sync/github", {"username": "someone", "token": "not-a-real-token"}),
    ]:
        assert_refused(client.start(method, path, headers=auth(user.id), json=body))

    assert job_count(user) == 2 and model.requests == []


def test_the_limit_is_each_users_own(client, seeded, reviews):
    first, second = new_user(), new_user()
    use_up(client, first)
    assert_refused(start_review(client, first))
    assert start_review(client, second).status_code == 202


def test_following_a_job_that_is_already_running_is_neither_counted_nor_refused(
    client, seeded, monkeypatch,
):
    release = threading.Event()

    async def slow(*args, **kwargs):
        while not release.is_set():
            await asyncio.sleep(0.01)
        return {"headline": "done"}
    monkeypatch.setattr("app.api.github.generate_github_portfolio_review", slow)
    monkeypatch.setattr(rate_limit.ai_work, "limit", 1)
    user = new_user()

    try:
        started = start_review(client, user)
        for _ in range(3):  # a reload, a double click
            again = start_review(client, user)
            assert again.status_code == 202 and again.json() == started.json()
        job = client.get(f"/background-jobs/{started.json()['job_id']}", headers=auth(user.id))
        assert job.status_code == 200
    finally:
        release.set()


def test_reading_pages_and_saved_results_is_not_limited(client, seeded, reviews):
    user = new_user()
    use_up(client, user)
    job = add_job(user, "Backend Engineer")
    for path in ("/github/workspace", "/profile/data", "/job-intelligence", f"/interview/kits/{job}"):
        assert client.get(path, headers=auth(user.id)).status_code == 200, path


def test_work_refused_for_the_daily_limit_does_not_also_count(client, seeded, monkeypatch, reviews):
    monkeypatch.setattr(llm_budget, "DAILY_CALLS", 3)
    user = new_user()
    spend(user, 3)
    for _ in range(5):
        response = start_review(client, user)
        assert response.status_code == 429 and "today's limit" in response.json()["detail"]
    assert rate_limit.ai_work.hit(str(user.id)) is None


def test_automatic_identity_refreshes_are_neither_counted_nor_refused(
    client, seeded, monkeypatch, reviews,
):
    refreshed = []

    async def refresh(db, user_id, **kwargs):
        refreshed.append(user_id)
    monkeypatch.setattr(identity_refresh, "refresh_identity", refresh)
    user = new_user()

    def trigger():  # on the app's event loop, where its job runs
        client.portal.call(identity_refresh.trigger_identity_refresh, user.id, "test")

    for _ in range(4):
        trigger()
    use_up(client, user)  # the user's own two are still there
    assert_refused(start_review(client, user))
    trigger()  # and a change to their data still refreshes
    assert job_count(user) == 4 + 2 + 1


@pytest.mark.parametrize("path, body", [
    ("/sync/leetcode", {"username": "someone"}),
    ("/sync/leetcode/manual", {"tag_counts": {"Never Heard Of It": 3}}),
])
def test_leetcode_syncs_count_because_new_topics_go_to_the_model(
    client, seeded, model, monkeypatch, reviews, path, body,
):
    async def fetched(*args, **kwargs):
        raise AssertionError("a refused sync must not reach LeetCode")
    monkeypatch.setattr("app.api.sync.sync_leetcode", fetched)
    user = new_user()
    use_up(client, user)

    assert_refused(client.post(path, headers=auth(user.id), json=body))
    assert model.requests == []


def test_the_resume_page_still_loads_and_says_why_role_fit_is_missing(
    client, seeded, model, monkeypatch, reviews,
):
    async def evidence(*args, **kwargs):
        return [{"skill": "Python", "confidence": 0.5, "sources": ["experience"]}]
    monkeypatch.setattr("app.api.resume.build_scoped_skill_evidence", evidence)
    user = new_user()

    async def upload(db):
        from app.models.facts import Resume
        db.add(Resume(user_id=user.id, raw_text="resume"))
        await db.commit()
    run(upload)
    use_up(client, user)

    page = client.get("/resume/workspace", headers=auth(user.id))
    assert page.status_code == 200, page.text
    assert page.json()["has_resume"] is True
    assert all(role["rationale"].startswith(REFUSED) for role in page.json()["role_fit"])
    assert model.requests == []
