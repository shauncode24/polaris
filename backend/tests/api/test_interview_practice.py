"""Practising a kit's questions: the review of an answer, and how much of the kit
is covered. Real database and routes; stand-in model.
"""
import json
import uuid

import httpx
import pytest
from openai import APITimeoutError, RateLimitError
from sqlalchemy import select

from app.core import llm, llm_budget
from app.models.interview_kit import InterviewQuestion, PracticeAttempt
from app.schemas.interview.kit import InterviewKitDraft
from app.services.interview.kit_evidence import map_evidence
from app.services.interview.kit_store import get_kit, save_new_kit
from app.services.interview.practice import review_answer
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from tests.api.test_evidence import auth, run
from tests.api.test_interview_kit_evidence import behavioral, hide_skill, skill_question, topic_question
from tests.api.test_resume_rewriting import POSTGRES, add_job
from tests.api.test_resume_selection import experience, new_user
from tests.llm_stub import api_error, model, reply  # noqa: F401 (model is a fixture)

ANSWER = (
    "During my internship the order page was slow. I added indexes in PostgreSQL, and the delay fell "
    "from 800ms to 210ms."
)
HEADINGS = ["Context", "The problem", "What you did", "Decisions and trade-offs", "Result", "What you would change"]
QUOTES = {"Context": "During my internship", "The problem": "the order page was slow",
          "What you did": "I added indexes in PostgreSQL", "Result": "fell from 800ms to 210ms"}


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "test-key")


def review(quotes=QUOTES, headings=HEADINGS, notes=None, overall="Say what else you considered."):
    return {
        "headings": [
            {"heading": heading, "covered": heading in quotes, "quote": quotes.get(heading, ""),
             "note": (notes or {}).get(heading, f"A note on {heading.lower()}.")}
            for heading in headings
        ],
        "overall": overall,
    }


def practising(*questions):
    """A user with a role that shows PostgreSQL, and a saved kit of these
    questions. Returns (user, job, the saved questions' ids).
    """
    user = new_user()
    experience(user, "Backend Intern", ["Postgres"], [
        "Cut latency from 800ms to 210ms by adding indexes to PostgreSQL.", "Led the returns work.",
    ], company="Northwind")
    job = add_job(user, [POSTGRES])
    questions = list(questions) or [skill_question("postgres")]

    async def go(db):
        mapping = await map_evidence(db, user.id, JobIntelligenceProfile(), questions)
        draft = InterviewKitDraft(seniority="mid", evidence_mapped_at=mapping.mapped_at, questions=[
            q.model_copy(update={"evidence_refs": refs, "thin_evidence": not refs})
            for q, refs in zip(questions, mapping.refs)
        ])
        saved = await save_new_kit(db, user.id, uuid.UUID(job), draft)
        return [q.id for q in saved.questions]

    return user, job, run(go)


def submit(client, user, question_id, answer=ANSWER):
    return client.post(f"/interview/questions/{question_id}/attempts", json={"answer": answer},
                       headers=auth(user.id))


def progress(client, user, job, version=None):
    query = f"?version={version}" if version else ""
    return client.get(f"/interview/kits/{job}/progress{query}", headers=auth(user.id))


def covered(attempt) -> list[str]:
    return [h["heading"] for h in attempt["feedback"]["headings"] if h["covered"]]


def heading(attempt, name) -> dict:
    return next(h for h in attempt["feedback"]["headings"] if h["heading"] == name)


# --- the review ---------------------------------------------------------------

def test_the_score_is_the_share_of_headings_the_answer_covers(client, model):
    user, _job, (question,) = practising()
    model.will(review())

    response = submit(client, user, question)

    assert response.status_code == 200, response.text[:300]
    attempt = response.json()
    assert (attempt["question_id"], attempt["answer"], attempt["score"]) == (str(question), ANSWER, 0.67)
    assert covered(attempt) == list(QUOTES)
    assert heading(attempt, "Result")["quote"] == "fell from 800ms to 210ms"
    assert heading(attempt, "Result")["note"] == "A note on result."
    assert heading(attempt, "What you would change")["quote"] is None
    assert heading(attempt, "Result")["prompt"]
    assert attempt["feedback"]["overall"] == "Say what else you considered."
    assert attempt["feedback"]["notice"] is None


def test_the_model_is_sent_the_question_its_headings_the_matched_work_and_the_answer(client, model):
    user, _job, (question,) = practising()
    model.will(review())

    submit(client, user, question)

    sent = json.loads(model.requests[-1]["messages"][1]["content"])
    assert set(sent) == {"category", "question", "headings", "record", "answer"}
    assert (sent["answer"], [h["heading"] for h in sent["headings"]]) == (ANSWER, HEADINGS)
    assert "Cut latency from 800ms to 210ms by adding indexes to PostgreSQL." in sent["record"]
    assert user.email not in json.dumps(sent)


@pytest.mark.parametrize("quote", [
    "I chose indexes over a cache",  # not in the answer
    "800ms to 90ms",  # altered
    "indexes",  # too short to show anything
    "",
    "added indexes in Postgre",  # part of a word
])
def test_a_heading_counts_only_with_words_that_are_in_the_answer(client, model, quote):
    user, _job, (question,) = practising()
    model.will(review({"Decisions and trade-offs": quote}))

    attempt = submit(client, user, question).json()

    assert (covered(attempt), attempt["score"]) == ([], 0)
    # Its remark was written for a covered part, so it is not shown.
    assert heading(attempt, "Decisions and trade-offs")["note"] is None


def test_a_quote_may_differ_in_case_spacing_and_punctuation(client, model):
    user, _job, (question,) = practising()
    model.will(review({"What you did": "i added  indexes in postgresql,", "Result": "“fell from 800ms to 210ms.”"}))

    assert covered(submit(client, user, question).json()) == ["What you did", "Result"]


def test_a_quote_given_for_a_heading_said_not_to_be_covered_counts_for_nothing(client, model):
    user, _job, (question,) = practising()
    verdict = review({})
    for entry in verdict["headings"]:
        entry["quote"] = "the order page was slow"
    model.will(verdict)

    assert submit(client, user, question).json()["score"] == 0


@pytest.mark.parametrize("remark", [
    "Mention that this saved 40% of the cost.",
    "Say how you moved it to Kafka.",
])
def test_a_remark_that_brings_something_in_is_dropped(client, model, remark):
    user, _job, (question,) = practising()
    model.will(review(notes={"Result": remark}, overall=remark))

    attempt = submit(client, user, question).json()

    assert heading(attempt, "Result")["note"] is None
    assert attempt["feedback"]["overall"] is None
    assert heading(attempt, "Context")["note"] == "A note on context."
    assert attempt["score"] == 0.67


def test_a_remark_may_repeat_the_record_the_question_and_the_answer(client, model):
    user, _job, (question,) = practising()
    remark = "Explain why PostgreSQL got from 800ms to 210ms."
    model.will(review(notes={"Result": remark}))

    assert heading(submit(client, user, question).json(), "Result")["note"] == remark


def test_what_the_record_does_not_show_is_warned_about(client, model):
    user, _job, (question,) = practising()
    model.will(review({}))

    attempt = submit(client, user, question, "I moved everything to Kafka and cut costs by 40% that year.").json()

    feedback = attempt["feedback"]
    assert (feedback["unrecorded_figures"], feedback["unrecorded_technologies"]) == (["40%"], ["Kafka"])
    assert "40%" in feedback["warnings"][0] and "Kafka" in feedback["warnings"][1]


def test_an_answer_within_the_record_has_no_warnings(client, model):
    user, _job, (question,) = practising()
    model.will(review())

    assert submit(client, user, question).json()["feedback"]["warnings"] == []


def test_a_hidden_skill_counts_as_not_shown(client, model):
    user, _job, (question,) = practising()
    hide_skill(user, "postgres")
    model.will(review())

    assert submit(client, user, question).json()["feedback"]["unrecorded_technologies"] == ["PostgreSQL"]


def test_a_question_with_no_evidence_can_still_be_practised(client, model):
    user, _job, (question,) = practising(topic_question("Caching"))
    names = ["Context", "Requirements", "How you would build it", "Trade-offs", "What breaks first"]
    model.will(review({"Requirements": "the order page was slow"}, names))

    attempt = submit(client, user, question).json()

    assert attempt["score"] == 0.2
    assert json.loads(model.requests[-1]["messages"][1]["content"])["record"] == []


def test_headings_may_come_back_in_any_order_and_case(client, model):
    user, _job, (question,) = practising()
    verdict = review()
    verdict["headings"].reverse()
    for entry in verdict["headings"]:
        entry["heading"] = entry["heading"].upper()
    verdict["headings"].append({"heading": "Charisma", "covered": True, "quote": ANSWER, "note": ""})
    model.will(verdict)

    attempt = submit(client, user, question).json()

    assert [h["heading"] for h in attempt["feedback"]["headings"]] == HEADINGS
    assert attempt["score"] == 0.67


# --- when the model can't be used ---------------------------------------------

@pytest.mark.parametrize("failure", [
    [api_error(RateLimitError, 429)],
    [APITimeoutError(request=httpx.Request("POST", "http://llm.invalid"))],
    ["nonsense", "nonsense"],
    [review(headings=HEADINGS[:-1])] * 2,  # a heading left out
    [reply(review(), finish_reason="length")] * 2,
], ids=["rate limited", "too slow", "not json", "heading missing", "cut off"])
def test_without_a_review_the_answer_is_saved_unscored_with_the_rule_check(client, model, failure):
    user, _job, (question,) = practising()
    model.will(*failure)

    response = submit(client, user, question, "I moved everything to Kafka that year, then went home.")

    assert response.status_code == 200, response.text[:300]
    attempt = response.json()
    assert attempt["score"] is None
    assert "no score" in attempt["feedback"]["notice"]
    assert attempt["feedback"]["unrecorded_technologies"] == ["Kafka"]
    assert {h["covered"] for h in attempt["feedback"]["headings"]} == {None}
    assert len(client.get(f"/interview/questions/{question}/attempts", headers=auth(user.id)).json()) == 1


def test_a_user_out_of_calls_can_still_practise(client, model, monkeypatch):
    user, _job, (question,) = practising()

    async def none_left(_user_id):
        return None

    async def no_calls(_user_id):
        return False
    monkeypatch.setattr(llm_budget, "reserve", none_left)
    monkeypatch.setattr(llm_budget, "has_calls_left", no_calls)

    attempt = submit(client, user, question).json()

    assert "today's limit" in attempt["feedback"]["notice"]
    assert model.requests == []


# --- saving and reading -------------------------------------------------------

def test_every_attempt_is_kept_newest_first(client, model):
    user, _job, (question,) = practising()
    model.will(review({}), review())
    first = submit(client, user, question).json()
    second = submit(client, user, question, ANSWER + " I would measure write cost next.").json()

    listed = client.get(f"/interview/questions/{question}/attempts", headers=auth(user.id)).json()

    assert [a["id"] for a in listed] == [second["id"], first["id"]]
    assert listed[1] == first


@pytest.mark.parametrize("answer", ["", "   ", "Too short.", "x" * 5001])
def test_an_answer_too_short_or_long_is_refused(client, model, answer):
    user, _job, (question,) = practising()

    assert submit(client, user, question, answer).status_code == 422
    assert model.requests == []


def test_another_users_question_cannot_be_practised_or_read(client, model):
    owner, job, (question,) = practising()
    other = new_user()

    assert submit(client, other, question).status_code == 404
    assert client.get(f"/interview/questions/{question}/attempts", headers=auth(other.id)).status_code == 404
    assert progress(client, other, job).status_code == 404
    assert submit(client, owner, uuid.uuid4()).status_code == 404
    assert model.requests == []


def test_nothing_is_saved_for_a_question_deleted_during_its_review(seeded, monkeypatch):
    user, job, (question,) = practising()

    async def delete_then_answer(**_request):
        assert (await _delete(question))
        return reply(review())

    async def _delete(question_id):
        from sqlalchemy import delete
        from tests.api.conftest import _new_engine
        engine = _new_engine()
        async with engine.begin() as connection:
            await connection.execute(delete(InterviewQuestion).where(InterviewQuestion.id == question_id))
        await engine.dispose()
        return True

    monkeypatch.setattr(llm, "chat_completion", delete_then_answer)

    async def go(db):
        return await review_answer(db, user.id, question, ANSWER)

    assert run(go) is None


def test_deleting_the_job_deletes_the_attempts(client, model):
    user, job, (question,) = practising()
    model.will(review())
    submit(client, user, question)

    assert client.delete(f"/job-intelligence/{job}", headers=auth(user.id)).status_code == 200

    async def left(db):
        return list(await db.scalars(select(PracticeAttempt).where(PracticeAttempt.user_id == user.id)))
    assert run(left) == []


# --- coverage -------------------------------------------------------------------

def scored(score_headings):
    return review({h: "the order page was slow" for h in HEADINGS[:score_headings]})


def test_progress_counts_what_has_been_practised_in_each_category(client, model):
    user, job, ids = practising(
        skill_question("postgres"), skill_question("postgres", topic="Again"), behavioral("leadership"),
        topic_question("Caching"),
    )

    before = progress(client, user, job).json()
    assert (before["total"], before["practised"], before["weakest"]) == (4, 0, None)
    assert [(c["category"], c["total"], c["practised"], c["average_score"]) for c in before["categories"]] == [
        ("technical_depth", 2, 0, None), ("system_design", 1, 0, None), ("behavioral", 1, 0, None)]
    assert [q["question_id"] for q in before["questions"]] == [str(i) for i in ids]

    model.will(scored(6), scored(3))
    submit(client, user, ids[0])
    submit(client, user, ids[1])
    after = progress(client, user, job).json()

    assert (after["version"], after["practised"]) == (1, 2)
    technical = after["categories"][0]
    assert (technical["practised"], technical["average_score"]) == (2, 0.75)
    assert [(q["attempts"], q["latest_score"]) for q in after["questions"]] == [
        (1, 1.0), (1, 0.5), (0, None), (0, None)]
    assert after["weakest"] == "system_design"  # first of the two not practised


def test_the_weakest_area_is_the_one_answered_least_well(client, model):
    user, job, (technical, design) = practising(skill_question("postgres"), topic_question("Caching"))
    names = ["Context", "Requirements", "How you would build it", "Trade-offs", "What breaks first"]
    model.will(scored(6), review({"Requirements": "the order page was slow"}, names))

    submit(client, user, technical)
    submit(client, user, design)

    assert progress(client, user, job).json()["weakest"] == "system_design"


def test_categories_that_stand_alike_have_no_weakest(client, model):
    user, job, ids = practising(skill_question("postgres"), behavioral("leadership"))
    names = ["Situation", "Your task", "What you did", "Result", "What you learned"]
    model.will(review({}), review({}, names))

    for question in ids:
        submit(client, user, question)

    assert progress(client, user, job).json()["weakest"] is None


def test_the_latest_scored_attempt_is_a_questions_score(client, model):
    user, job, (question,) = practising()
    model.will(scored(6), scored(3), api_error(RateLimitError, 429))
    for number in range(3):
        submit(client, user, question, f"{ANSWER} Take {'one two three'.split()[number]}.")

    found = progress(client, user, job).json()["questions"][0]

    assert (found["attempts"], found["latest_score"]) == (3, 0.5)


def test_an_unscored_attempt_still_counts_as_practised(client, model):
    user, job, (question,) = practising()
    model.will(api_error(RateLimitError, 429))
    submit(client, user, question)

    category = progress(client, user, job).json()["categories"][0]

    assert (category["practised"], category["average_score"]) == (1, None)


def test_each_version_of_a_kit_has_its_own_progress(client, model):
    user, job, (question,) = practising()
    model.will(scored(6))
    submit(client, user, question)

    async def again(db):
        await save_new_kit(db, user.id, uuid.UUID(job), InterviewKitDraft(
            seniority="mid", questions=[skill_question("postgres")]))
        return await get_kit(db, user.id, uuid.UUID(job))
    run(again)

    assert (progress(client, user, job).json()["version"], progress(client, user, job).json()["practised"]) == (2, 0)
    assert progress(client, user, job, 1).json()["practised"] == 1
    assert progress(client, user, job, 3).status_code == 404
