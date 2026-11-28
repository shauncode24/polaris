"""Generating and storing the interview kit for a job. Real database; stand-in model."""
import json
import uuid

import httpx
import pytest
from openai import APITimeoutError, AuthenticationError, InternalServerError, RateLimitError
from sqlalchemy import select

from app.core import llm, llm_budget
from app.models.interview_kit import InterviewKit, InterviewQuestion
from app.services.interview.kit_generation import generate_interview_kit
from app.services.interview.kit_store import get_kit, save_new_kit
from tests.api.test_evidence import auth, run
from tests.api.test_resume_rewriting import POSTGRES, add_job
from tests.api.test_resume_selection import experience, new_user, project
from tests.llm_stub import api_error, model, reply  # noqa: F401 (model is a fixture)

REST = ("REST APIs", "rest_api")
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


class Worder:
    """Answers with a wording for every question it is asked, which `change` may alter."""

    def __init__(self, change=lambda asked, wordings: wordings):
        self.change = change
        self.asked: list[dict] = []

    async def __call__(self, **request):
        asked = json.loads(request["messages"][1]["content"])
        self.asked.append(asked)
        wordings = {q["id"]: f"About {q['topic']}: how would you handle it? ({q['id']})" for q in asked["questions"]}
        wordings = self.change(asked, wordings)
        return reply({"questions": [{"id": slot, "question": text} for slot, text in wordings.items()]})


@pytest.fixture
def worder(monkeypatch):
    def install(*args):
        stand_in = Worder(*args)
        monkeypatch.setattr(llm, "chat_completion", stand_in)
        return stand_in
    return install


def a_job(user=None):
    user = user or new_user()
    return user, add_job(user, [POSTGRES, REST])


def generate(user, job_id):
    async def go(db):
        return await generate_interview_kit(db, user.id, uuid.UUID(job_id))
    return run(go)


def save(user, job_id, draft):
    async def go(db):
        return await save_new_kit(db, user.id, uuid.UUID(job_id), draft)
    return run(go)


def load(user, job_id, version=None):
    async def go(db):
        return await get_kit(db, user.id, uuid.UUID(job_id), version)
    return run(go)


def by_topic(draft, topic):
    return next(q for q in draft.questions if q.topic == topic)


def test_the_model_words_each_question_and_nothing_else_changes(seeded, model, worder):
    user, job = a_job()
    model.will(api_error(RateLimitError, 429))
    outline = generate(user, job).questions
    stand_in = worder()

    draft = generate(user, job)

    assert draft.notice is None
    assert {q.origin for q in draft.questions} == {"model"}
    assert [q.text for q in draft.questions] == [
        f"About {q.topic}: how would you handle it? (q{n})" for n, q in enumerate(outline, start=1)]
    unchanged = {"text", "origin"}
    assert [q.model_dump(exclude=unchanged) for q in draft.questions] == [
        q.model_dump(exclude=unchanged) for q in outline]
    assert len(stand_in.asked) == 1


def test_only_the_job_is_sent_to_word_the_questions(seeded, worder):
    user = new_user()
    experience(user, "Secret Role", ["Kubernetes"], ["Ran the secret cluster."], company="Hidden Co")
    project(user, "Quiet Project", ["Redis"], "Cached results in Redis.")
    _user, job = a_job(user)
    stand_in = worder()

    generate(user, job)

    asked = stand_in.asked[0]
    assert set(asked) == {"role", "seniority", "responsibilities", "questions"}
    assert set(asked["questions"][0]) == {"id", "category", "topic", "outline"}
    everything = json.dumps(asked)
    for unsent in ("Secret Role", "Hidden Co", "Quiet Project", "secret cluster", "Redis", "Sam Rivera", "Globex"):
        assert unsent not in everything


UNUSABLE = {
    "too short": "Why?",
    "too long": "Postgres " * 60,
    "not about the skill": "How would you plan the team's next offsite?",
    "empty": "   ",
}


@pytest.mark.parametrize("text", UNUSABLE.values(), ids=UNUSABLE)
def test_a_wording_that_cannot_be_used_leaves_the_standard_one(seeded, worder, text):
    user, job = a_job()
    worder(lambda asked, wordings: {**wordings, "q1": text})

    draft = generate(user, job)

    first, rest = draft.questions[0], draft.questions[1:]
    assert (first.topic, first.origin) == ("PostgreSQL", "outline")
    assert "PostgreSQL" in first.text
    assert {q.origin for q in rest} == {"model"}
    assert draft.notice.startswith(f"1 of {len(draft.questions)} questions use standard wording")


@pytest.mark.parametrize("text", [
    "How do you version a REST API without breaking its callers?",
    "How would you secure a REST‑API used by other teams?",  # a non-breaking hyphen
    "What makes the postgres query planner choose an index scan?",
])
def test_a_technical_question_may_name_its_skill_in_another_form(seeded, worder, text):
    user, job = a_job()
    slot = "q1" if "postgres" in text else "q2"
    worder(lambda asked, wordings: {**wordings, slot: text})

    draft = generate(user, job)

    assert draft.questions[int(slot[1]) - 1].text == text
    assert draft.notice is None


def test_replies_for_unknown_or_repeated_questions_are_ignored(seeded, model):
    user, job = a_job()
    same = "How would you tune Postgres or a REST API?"
    model.will({"questions": [
        {"id": "q99", "question": "A question nobody asked for, about Postgres?"},
        "not an entry",
        {"id": 1, "question": same},
        {"id": "q1", "question": same},
        {"id": "q1", "question": "A second go at Postgres, to be ignored?"},
        {"id": "q2", "question": same.upper()},
    ]})

    draft = generate(user, job)

    assert [q.text for q in draft.questions if q.origin == "model"] == [same]
    assert draft.questions[0].text == same
    assert draft.notice.startswith(f"{len(draft.questions) - 1} of {len(draft.questions)}")


@pytest.mark.parametrize("unreadable", [
    "nonsense",
    {"questions": []},
    {"questions": "none"},
    {"other": 1},
    reply({"questions": [{"id": "q1", "question": "How do you tune Postgres?"}]}, finish_reason="length"),
], ids=["not json", "no questions", "not a list", "missing", "cut off"])
def test_unusable_replies_are_asked_for_again_then_give_the_standard_kit(seeded, model, unreadable):
    user, job = a_job()
    model.will(unreadable, unreadable)

    draft = generate(user, job)

    assert len(model.requests) == 2
    assert {q.origin for q in draft.questions} == {"outline"}
    assert draft.notice.startswith("The questions use standard wording")
    assert "unreadable" in draft.notice


def test_a_second_reply_can_still_be_used(seeded, model):
    user, job = a_job()
    model.will("nonsense", {"questions": [{"id": "q1", "question": "How do you tune Postgres?"}]})

    assert generate(user, job).questions[0].text == "How do you tune Postgres?"


@pytest.mark.parametrize("error", UNAVAILABLE.values(), ids=UNAVAILABLE)
def test_an_unavailable_model_gives_the_standard_kit_with_a_notice(seeded, model, error):
    user, job = a_job()
    model.will(error)

    draft = generate(user, job)

    assert {q.category for q in draft.questions} == {
        "technical_depth", "system_design", "behavioral", "role_specific"}
    assert {q.origin for q in draft.questions} == {"outline"}
    assert draft.notice.startswith("The questions use standard wording")
    assert "provider detail" not in draft.notice
    assert len(model.requests) == 1


def test_a_missing_key_is_named_in_the_notice(seeded, model, monkeypatch):
    user, job = a_job()
    monkeypatch.setattr(llm, "API_KEY", "")

    draft = generate(user, job)

    assert "GROQ_API_KEY" in draft.notice
    assert model.requests == []


def test_a_user_out_of_calls_still_gets_a_kit(seeded, model, monkeypatch):
    user, job = a_job()

    async def none_left(_user_id):
        return None
    monkeypatch.setattr(llm_budget, "reserve", none_left)
    token = llm_budget.current_user.set(user.id)
    try:
        draft = generate(user, job)
    finally:
        llm_budget.current_user.reset(token)

    assert "today's limit" in draft.notice
    assert draft.questions
    assert model.requests == []


def test_another_users_job_gives_nothing(seeded, model):
    _user, job = a_job()

    assert generate(new_user(), job) is None
    assert model.requests == []


def test_a_kit_is_saved_and_read_back_in_order(seeded, worder):
    user, job = a_job()
    worder(lambda asked, wordings: {slot: text for slot, text in wordings.items() if slot != "q2"})
    draft = generate(user, job)

    save(user, job, draft)
    saved = load(user, job)

    assert (saved.kit.version, saved.kit.seniority, saved.kit.notice) == (1, draft.seniority, draft.notice)
    assert [q.position for q in saved.questions] == list(range(len(draft.questions)))
    assert [(q.category, q.topic, q.text, q.skills, q.competencies, q.origin) for q in saved.questions] == [
        (q.category, q.topic, q.text, q.skills, q.competencies, q.origin) for q in draft.questions]
    # This user has no work to match.
    assert {(tuple(q.evidence_refs), q.thin_evidence) for q in saved.questions} == {((), True)}


def test_each_save_is_a_new_version_and_earlier_questions_stay(seeded, model):
    user, job = a_job()
    model.will(*[api_error(RateLimitError, 429)] * 2)
    first, second = generate(user, job), generate(user, job)

    versions = [save(user, job, first).kit.version, save(user, job, second).kit.version]

    assert versions == [1, 2]
    assert load(user, job).kit.version == 2
    earlier = {q.id for q in load(user, job, 1).questions}
    assert earlier and not earlier & {q.id for q in load(user, job, 2).questions}
    assert load(user, job, 3) is None


def test_another_users_kit_is_out_of_reach(seeded, model):
    owner, job = a_job()
    model.will(api_error(RateLimitError, 429))
    draft = generate(owner, job)
    save(owner, job, draft)
    other = new_user()

    assert save(other, job, draft) is None
    assert load(other, job) is None
    assert load(owner, job).kit.version == 1


def test_deleting_the_job_deletes_its_kits_and_questions(client, seeded, model):
    user, job = a_job()
    model.will(api_error(RateLimitError, 429))
    saved = save(user, job, generate(user, job))

    assert client.delete(f"/job-intelligence/{job}", headers=auth(user.id)).status_code == 200

    async def left(db):
        kits = await db.scalars(select(InterviewKit).where(InterviewKit.user_id == user.id))
        questions = await db.scalars(select(InterviewQuestion).where(InterviewQuestion.kit_id == saved.kit.id))
        return list(kits), list(questions)

    assert run(left) == ([], [])
