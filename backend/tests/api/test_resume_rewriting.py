"""Rewording a tailored resume's bullets. Real database; stand-in model."""
import json
import uuid
from datetime import datetime, timezone

import pytest
from openai import RateLimitError

from app.core import llm, llm_budget
from app.models.facts import UserSkillOverride
from app.models.job_intelligence import JobIntelligenceProfileRow
from app.services.resume.rewriting import rewrite_bullets
from tests.api.test_evidence import run
from tests.api.test_resume_selection import evidence, experience, new_user, project, select_
from tests.api.test_skill_gap_evidence import _skill
from tests.llm_stub import api_error, model  # noqa: F401 (model is a fixture)


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "test-key")


def add_job(user, required, nice=(), role="Backend Engineer"):
    """A job whose skills are (its own wording, canonical name), as extraction stores them."""
    def entries(skills, kind):
        return [{"raw": raw, "canonical": canonical, "category": "Other", "curriculum_phase": "core",
                 "requirement_type": kind} for raw, canonical in skills]

    async def go(db):
        job = JobIntelligenceProfileRow(
            user_id=user.id, source_text_hash=uuid.uuid4().hex, created_at=datetime.now(timezone.utc),
            profile_json={
                "role": role, "company": "Globex",
                "enriched_required_skills": entries(required, "required"),
                "enriched_nice_to_have": entries(nice, "nice_to_have"),
            },
        )
        db.add(job)
        await db.commit()
        return str(job.id)
    return run(go)


POSTGRES, REDIS = ("PostgreSQL", "postgres"), ("Redis", "redis")
DOCKER, KUBERNETES = ("Docker", "docker"), ("Kubernetes", "kubernetes")


def rewrite(user, job_id, document):
    async def go(db):
        return await rewrite_bullets(db, user.id, uuid.UUID(job_id), document)
    return run(go)


def sent(model) -> list[dict]:
    return [json.loads(request["messages"][1]["content"]) for request in model.requests]


def resume(bullets):
    """A user with one role holding `bullets`, a job, and the chosen document."""
    user = new_user()
    experience(user, "Engineer", bullets=bullets)
    job = add_job(user, [POSTGRES])
    return user, job, select_(user, job).document


def test_a_rewrite_is_stored_as_a_pending_suggestion(seeded, model):
    user, job, document = resume(["Tuned Postgres queries."])
    model.will({"rewrite": "Optimised PostgreSQL queries."})

    result = rewrite(user, job, document)

    line = result.document.experience[0].bullets[0]
    assert (line.original, line.rewrite, line.decision) == (
        "Tuned Postgres queries.", "Optimised PostgreSQL queries.", "pending")
    assert line.text == "Tuned Postgres queries."  # not on the resume until accepted
    before = document.experience[0].bullets[0]
    assert (line.id, line.sources) == (before.id, before.sources)
    assert before.rewrite is None  # the document passed in is left alone
    assert result.problem is None


def test_each_call_sees_one_bullet_and_only_the_job_terms_it_mentions(seeded, model):
    user = new_user()
    experience(user, "Secret Role", ["Kubernetes"], ["Tuned postgres queries.", "Shipped Docker images."],
               company="Hidden Co")
    project(user, "Quiet Project", ["Redis"], "Cached results in Redis.")
    job = add_job(user, [POSTGRES, REDIS, KUBERNETES], nice=[DOCKER])
    document = select_(user, job).document
    model.will(*[{"rewrite": "Reworded."}] * 3)

    rewrite(user, job, document)

    assert sorted(sent(model), key=lambda p: p["bullet"]) == [
        {"bullet": "Cached results in Redis.", "job_terms": [{"term": "Redis", "in_bullet": "Redis"}]},
        {"bullet": "Shipped Docker images.", "job_terms": [{"term": "Docker", "in_bullet": "Docker"}]},
        {"bullet": "Tuned postgres queries.", "job_terms": [{"term": "PostgreSQL", "in_bullet": "postgres"}]},
    ]
    everything = json.dumps([request["messages"] for request in model.requests])
    for unsent in ("Secret Role", "Hidden Co", "Quiet Project", "Backend Engineer", "Kubernetes"):
        assert unsent not in everything


def test_a_bullet_showing_nothing_the_job_asks_for_is_not_sent(seeded, model):
    user, job, document = resume(["Organised the team offsite."])

    result = rewrite(user, job, document)

    assert model.requests == []
    assert result.document.experience[0].bullets[0].rewrite is None


def test_a_hidden_skill_is_not_offered_to_the_model(seeded, model):
    user = new_user()
    item = experience(user, "Engineer", bullets=["Ran Docker and Postgres."])
    evidence(user, "docker", "experience", item)

    async def hide(db):
        skill = await _skill(db, "docker")
        db.add(UserSkillOverride(user_id=user.id, skill_id=skill.id, is_hidden=True,
                                 updated_at=datetime.now(timezone.utc)))
        await db.commit()
    run(hide)
    job = add_job(user, [POSTGRES, DOCKER])
    model.will({"rewrite": "Reworded."})

    rewrite(user, job, select_(user, job).document)

    assert [t["term"] for t in sent(model)[0]["job_terms"]] == ["PostgreSQL"]


@pytest.mark.parametrize(("bullet", "found"), [
    ("Designed REST APIs.", "REST APIs"),  # the longest spelling, not just "REST"
    ("Designed a RESTful service.", "RESTful"),
    ("Wrote restaurant listings.", None),  # part of another word
    ("Moved restaurant search to Rest.", "Rest"),  # the word itself, not the earlier part of one
])
def test_the_matched_wording_is_reported_whole(seeded, model, bullet, found):
    user = new_user()
    experience(user, "Engineer", bullets=[bullet])
    job = add_job(user, [("REST", "rest_api")])
    if found:
        model.will({"rewrite": "Reworded."})

    rewrite(user, job, select_(user, job).document)

    assert [t["in_bullet"] for p in sent(model) for t in p["job_terms"]] == ([found] if found else [])


def test_the_jobs_own_wording_counts_as_a_mention(seeded, model):
    user = new_user()
    experience(user, "Engineer", bullets=["Wrote Terraform HCL modules."])
    job = add_job(user, [("Terraform HCL", f"made_up_{uuid.uuid4().hex[:8]}")])
    model.will({"rewrite": "Reworded."})

    rewrite(user, job, select_(user, job).document)

    assert sent(model)[0]["job_terms"] == [{"term": "Terraform HCL", "in_bullet": "Terraform HCL"}]


def test_an_unchanged_reply_leaves_no_suggestion(seeded, model):
    user, job, document = resume(["Tuned Postgres queries."])
    model.will({"rewrite": "  tuned Postgres   queries "})

    result = rewrite(user, job, document)

    assert result.document.experience[0].bullets[0].rewrite is None
    assert result.problem is None


def test_the_reply_is_tidied_into_one_line(seeded, model):
    user, job, document = resume(["Tuned Postgres queries."])
    model.will({"rewrite": "• Optimised PostgreSQL\n queries."})

    result = rewrite(user, job, document)

    assert result.document.experience[0].bullets[0].rewrite == "Optimised PostgreSQL queries."


@pytest.mark.parametrize("bad", [{"rewrite": ""}, {"rewrite": None}, {"rewrite": "x" * 500}, {}])
def test_an_unusable_reply_is_asked_for_again(seeded, model, bad):
    user, job, document = resume(["Tuned Postgres queries."])
    model.will(bad, {"rewrite": "Optimised PostgreSQL queries."})

    result = rewrite(user, job, document)

    assert result.document.experience[0].bullets[0].rewrite == "Optimised PostgreSQL queries."
    assert len(model.requests) == 2


def test_one_bad_bullet_does_not_stop_the_others(seeded, model):
    user, job, document = resume(["Tuned Postgres queries.", "Backed up Postgres."])
    model.will("nonsense", "nonsense", {"rewrite": "Backed up PostgreSQL."})

    result = rewrite(user, job, document)

    assert [line.rewrite for line in result.document.experience[0].bullets] == [None, "Backed up PostgreSQL."]
    assert "unreadable" in result.problem


def test_an_unavailable_model_stops_the_run_and_keeps_what_was_written(seeded, model):
    user, job, document = resume(["Tuned Postgres queries.", "Backed up Postgres.", "Upgraded Postgres."])
    model.will({"rewrite": "Optimised PostgreSQL queries."}, api_error(RateLimitError, 429))

    result = rewrite(user, job, document)

    assert [line.rewrite for line in result.document.experience[0].bullets] == [
        "Optimised PostgreSQL queries.", None, None]
    assert "usage limit" in result.problem
    assert len(model.requests) == 2


def test_a_missing_key_is_reported_without_any_request(seeded, model, monkeypatch):
    user, job, document = resume(["Tuned Postgres queries."])
    monkeypatch.setattr(llm, "API_KEY", "")

    result = rewrite(user, job, document)

    assert "GROQ_API_KEY" in result.problem
    assert model.requests == []


def test_running_out_of_calls_is_not_hidden(seeded, model, monkeypatch):
    user, job, document = resume(["Tuned Postgres queries."])

    async def none_left(_user_id):
        return None
    monkeypatch.setattr(llm_budget, "reserve", none_left)
    token = llm_budget.current_user.set(user.id)
    try:
        with pytest.raises(llm.LLMBudgetError):
            rewrite(user, job, document)
    finally:
        llm_budget.current_user.reset(token)


def test_another_users_job_gives_nothing(seeded, model):
    _user, job, document = resume(["Tuned Postgres queries."])

    assert rewrite(new_user(), job, document) is None
    assert model.requests == []
