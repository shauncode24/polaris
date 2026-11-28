"""The routes behind the interview kit page. Real database; stand-in model."""
import pytest
from openai import RateLimitError

from app.core import llm, llm_budget
from app.models.facts import Project
from app.services.evidence.state import touch_evidence
from tests.api.test_evidence import auth, run
from tests.api.test_interview_kit_answers import kit_for
from tests.api.test_interview_kit_evidence import hide_skill, skill_question
from tests.api.test_resume_rewriting import POSTGRES, add_job
from tests.api.test_resume_selection import experience, new_user, project
from tests.llm_stub import api_error, model  # noqa: F401 (model is a fixture)

OFF = api_error(RateLimitError, 429)


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "test-key")


def a_job(*skills):
    user = new_user()
    return user, add_job(user, list(skills) or [POSTGRES])


def read(client, user, job, version=None):
    query = "" if version is None else f"?version={version}"
    return client.get(f"/interview/kits/{job}{query}", headers=auth(user.id))


def generate(client, user, job):
    response = client.post(f"/interview/kits/{job}", headers=auth(user.id))
    assert response.status_code == 200, response.text[:400]
    return response.json()


def rematch(client, user, job, version=1):
    return client.post(f"/interview/kits/{job}/versions/{version}/evidence", headers=auth(user.id))


def question(page, topic="PostgreSQL"):
    return next(q for q in page["kit"]["questions"] if q["topic"] == topic)


def test_a_job_without_a_kit_says_so(client, seeded):
    user, job = a_job()

    page = read(client, user, job).json()

    assert page == {"job": {"id": job, "role": "Backend Engineer", "company": "Globex"}, "versions": [], "kit": None}


def test_a_generated_kit_shows_each_question_with_its_evidence(client, model):
    user, job = a_job()
    # Wording fails; the role's own words are keyword-tagged, so nothing else is asked.
    experience(user, "Captain", bullets=["Led the Postgres migration."], company="Club")
    model.will(OFF)

    page = generate(client, user, job)

    kit = page["kit"]
    assert (page["versions"], kit["version"], kit["stale"], kit["practised"]) == ([1], 1, False, 0)
    assert kit["total"] == len(kit["questions"]) == sum(c["total"] for c in kit["categories"])
    assert "standard wording" in kit["notice"]
    found = question(page)
    assert (found["thin"], found["shows"], found["attempts"], found["latest_score"], found["origin"]) == (
        False, ["PostgreSQL"], 0, None, "outline")
    assert found["outline"]["story"]["title"] == "Captain at Club"
    thin = [q for q in kit["questions"] if q["thin"]]
    assert thin and all(q["shows"] == [] and q["outline"]["story"] is None for q in thin)
    assert read(client, user, job).json() == page


def test_each_generation_is_a_new_version_and_earlier_ones_can_be_opened(client, model):
    user, job = a_job()
    model.will(OFF, OFF)
    first = generate(client, user, job)

    second = generate(client, user, job)

    assert (second["versions"], second["kit"]["version"]) == ([2, 1], 2)
    assert read(client, user, job).json()["kit"]["version"] == 2
    earlier = read(client, user, job, 1).json()["kit"]
    assert [q["id"] for q in earlier["questions"]] == [q["id"] for q in first["kit"]["questions"]]
    assert read(client, user, job, 3).status_code == 404
    assert read(client, user, job, 0).status_code == 422


def test_matching_again_brings_the_kit_up_to_date(client, model):
    user, job = a_job()
    model.will(OFF)
    before = generate(client, user, job)
    assert question(before)["thin"]

    project(user, "Ledger", ["Postgres"], "Stores accounts in Postgres.", competency_tags=[])

    async def changed(db):
        await touch_evidence(db, user.id)
    run(changed)
    assert read(client, user, job).json()["kit"]["stale"]

    response = rematch(client, user, job)

    assert response.status_code == 200, response.text[:300]
    after = response.json()["kit"]
    assert (after["stale"], after["version"]) == (False, 1)
    assert [q["id"] for q in after["questions"]] == [q["id"] for q in before["kit"]["questions"]]
    assert question(response.json())["outline"]["story"]["title"] == "Ledger"


def test_evidence_removed_since_matching_shows_nothing(client, model):
    user, job = a_job()
    item = project(user, "Ledger", ["Postgres"], "Stores accounts in Postgres.", competency_tags=[])
    model.will(OFF)
    generate(client, user, job)

    async def hide(db):
        (await db.get(Project, item)).is_hidden = True
        await db.commit()
    run(hide)
    found = question(read(client, user, job).json())

    assert (found["shows"], found["outline"]["story"]) == ([], None)
    assert "removed or hidden" in found["outline"]["warnings"][0]


def test_a_skill_hidden_since_matching_is_not_listed(client, model):
    user, job = a_job()
    project(user, "Ledger", ["Postgres"], "Stores accounts in Postgres.", competency_tags=[])
    model.will(OFF)
    generate(client, user, job)

    hide_skill(user, "postgres")

    assert question(read(client, user, job).json())["shows"] == []


def test_the_other_skills_stay_listed_when_one_is_hidden(client):
    user = new_user()
    project(user, "Ledger", ["Postgres", "Redis"], "Used Postgres and Redis.", competency_tags=[])
    job = kit_for(user, skill_question("postgres", "redis"))
    # As the job writes a skill, where it names it.
    assert read(client, user, job).json()["kit"]["questions"][0]["shows"] == ["PostgreSQL", "redis"]

    hide_skill(user, "redis")

    assert read(client, user, job).json()["kit"]["questions"][0]["shows"] == ["PostgreSQL"]


def test_the_page_shows_how_practice_has_gone_on_each_question(client, model):
    user, job = a_job()
    model.will(OFF)
    page = generate(client, user, job)
    first = question(page)
    headings = [s["heading"] for s in first["outline"]["sections"]]
    answer = "I would start by reading the query plan before changing anything."
    model.will({"headings": [
        {"heading": h, "covered": h == headings[0], "quote": "reading the query plan", "note": ""}
        for h in headings
    ], "overall": ""})
    response = client.post(f"/interview/questions/{first['id']}/attempts", json={"answer": answer},
                           headers=auth(user.id))
    assert response.status_code == 200, response.text[:300]

    kit = read(client, user, job).json()["kit"]

    practised = next(q for q in kit["questions"] if q["id"] == first["id"])
    assert (practised["attempts"], practised["latest_score"]) == (1, response.json()["score"])
    assert practised["latest_score"] > 0
    assert (kit["practised"], kit["weakest"] is not None) == (1, True)
    assert all(q["attempts"] == 0 for q in kit["questions"] if q["id"] != first["id"])


def test_a_user_out_of_calls_can_still_make_and_match_a_kit(client, model, monkeypatch):
    user, job = a_job()

    async def none_left(_user_id):
        return None

    async def no_calls(_user_id):
        return False
    monkeypatch.setattr(llm_budget, "reserve", none_left)
    monkeypatch.setattr(llm_budget, "has_calls_left", no_calls)

    page = generate(client, user, job)

    assert "today's limit" in page["kit"]["notice"]
    assert rematch(client, user, job).status_code == 200
    assert model.requests == []


def test_another_users_job_and_kit_are_out_of_reach(client, model):
    owner, job = a_job()
    model.will(OFF)
    generate(client, owner, job)
    other = new_user()

    assert read(client, other, job).status_code == 404
    assert read(client, other, job, 1).status_code == 404
    assert client.post(f"/interview/kits/{job}", headers=auth(other.id)).status_code == 404
    assert rematch(client, other, job).status_code == 404
    assert rematch(client, owner, job, 2).status_code == 404
    assert read(client, owner, job).json()["versions"] == [1]
    assert len(model.requests) == 1
