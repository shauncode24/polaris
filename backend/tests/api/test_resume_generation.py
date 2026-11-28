"""The tailored resume still comes out when the model fails. Real database; stand-in model."""
import uuid

import httpx
import pytest
from openai import APITimeoutError, AuthenticationError, InternalServerError, RateLimitError

from app.core import llm, llm_budget
from app.services.resume.generation import generate_tailored_resume
from app.services.resume.tailored_store import document_of, save_new_version
from tests.api.test_evidence import run
from tests.api.test_resume_rewriting import POSTGRES, add_job
from tests.api.test_resume_selection import experience, new_user, project, select_
from tests.llm_stub import api_error, model  # noqa: F401 (model is a fixture)

BULLETS = ["Wrote the handover notes.", "Tuned Postgres queries.", "Backed up Postgres."]
RELEVANT_FIRST = ["Tuned Postgres queries.", "Backed up Postgres.", "Wrote the handover notes."]
UNAVAILABLE = {
    "rate limited": api_error(RateLimitError, 429),
    "server error": api_error(InternalServerError, 500),
    "bad key": api_error(AuthenticationError, 401),
    "too slow": APITimeoutError(request=httpx.Request("POST", "http://llm.invalid")),
    "anything else": RuntimeError("provider detail that users must not see"),
}


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "test-key")


def record():
    user = new_user()
    experience(user, "Engineer", bullets=BULLETS)
    project(user, "Ledger", ["Postgres"], "Stores accounts in Postgres.")
    return user, add_job(user, [POSTGRES])


def generate(user, job_id):
    async def go(db):
        return await generate_tailored_resume(db, user.id, uuid.UUID(job_id))
    return run(go)


def wording(document) -> list[str]:
    return [line.text for line in document.experience[0].bullets]


def comparable(selection) -> dict:
    """A selection without what differs between two runs, or marks a failure."""
    data = selection.model_dump(mode="json")
    for entry in [*data["document"]["experience"], *data["document"]["projects"]]:
        for line in entry["bullets"]:
            del line["id"]
    del data["document"]["notice"]
    return data


@pytest.mark.parametrize("error", UNAVAILABLE.values(), ids=UNAVAILABLE)
def test_an_unavailable_model_leaves_the_users_own_wording_most_relevant_first(seeded, model, error):
    user, job = record()
    model.will(error)

    result = generate(user, job)

    assert comparable(result) == comparable(select_(user, job))
    assert wording(result.document) == RELEVANT_FIRST
    assert result.document.notice.startswith("No bullets were reworded.")
    assert "own wording" in result.document.notice
    assert "provider detail" not in result.document.notice
    assert len(model.requests) == 1


def test_a_missing_key_is_named_in_the_notice(seeded, model, monkeypatch):
    user, job = record()
    monkeypatch.setattr(llm, "API_KEY", "")

    document = generate(user, job).document

    assert wording(document) == RELEVANT_FIRST
    assert "GROQ_API_KEY" in document.notice
    assert model.requests == []


def test_a_user_out_of_calls_still_gets_a_resume(seeded, model, monkeypatch):
    user, job = record()

    async def none_left(_user_id):
        return None
    monkeypatch.setattr(llm_budget, "reserve", none_left)
    token = llm_budget.current_user.set(user.id)
    try:
        document = generate(user, job).document
    finally:
        llm_budget.current_user.reset(token)

    assert wording(document) == RELEVANT_FIRST
    assert "today's limit" in document.notice
    assert model.requests == []


def test_rewrites_made_before_a_failure_are_kept(seeded, model):
    user, job = record()
    model.will({"rewrite": "Tuned PostgreSQL queries."}, api_error(RateLimitError, 429))

    document = generate(user, job).document

    assert document.experience[0].bullets[0].rewrite == "Tuned PostgreSQL queries."
    assert wording(document) == RELEVANT_FIRST  # a suggestion is not on the resume until accepted
    assert document.notice.startswith("Only some bullets")
    assert "usage limit" in document.notice


def test_unreadable_replies_end_in_the_same_fallback(seeded, model):
    user, job = record()
    model.will(*["nonsense"] * 6)

    document = generate(user, job).document

    assert wording(document) == RELEVANT_FIRST
    assert document.notice.startswith("No bullets were reworded.")
    assert "unreadable" in document.notice


def test_there_is_no_notice_when_nothing_fails(seeded, model):
    user, job = record()
    model.will(
        {"rewrite": "Tuned PostgreSQL queries."},
        {"rewrite": "Backed up 40 PostgreSQL servers."},  # removed for its figure, which is no failure
        {"rewrite": "Stores accounts in PostgreSQL."},
    )

    document = generate(user, job).document

    assert document.notice is None
    assert [bool(line.rewrite) for line in document.lines()] == [True, False, False, True]  # the third wasn't sent


def test_the_notice_is_saved_with_the_resume(seeded, model):
    user, job = record()
    model.will(api_error(RateLimitError, 429))
    document = generate(user, job).document

    async def go(db):
        return document_of(await save_new_version(db, user.id, uuid.UUID(job), document))

    saved = run(go)

    assert saved == document
    assert saved.notice


def test_another_users_job_gives_nothing(seeded, model):
    _user, job = record()

    assert generate(new_user(), job) is None
    assert model.requests == []
