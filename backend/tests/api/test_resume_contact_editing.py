"""Contact details on the tailored resume, and skills named as the job writes
them. Through the API; real database; stand-in model.
"""
import pytest

from app.core import llm
from app.models.facts import User
from tests.api.test_evidence import auth, run
from tests.api.test_resume_rewriting import add_job
from tests.api.test_resume_selection import evidence, experience, new_user, project, select_
from tests.llm_stub import model  # noqa: F401 (model is a fixture)

PHONE = "+91 98765 43210"
LINKEDIN = "https://www.linkedin.com/in/sam"


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "test-key")


def record(**fields):
    user = new_user(**fields)
    experience(user, "Engineer", bullets=["Wrote notes."])
    return user, add_job(user, [("Haskell", "haskell")])  # nothing to reword


def generate(client, user, job) -> dict:
    response = client.post(f"/tailored-resumes/{job}", headers=auth(user.id))
    assert response.status_code == 200, response.text[:300]
    return response.json()["resume"]


def patch(client, user, job, body, version=1):
    return client.patch(f"/tailored-resumes/{job}/versions/{version}", json=body, headers=auth(user.id))


def stored(user) -> tuple:
    async def go(db):
        row = await db.get(User, user.id)
        return row.phone, row.linkedin_url
    return run(go)


def links(resume) -> list[tuple[str, str]]:
    return [(link["label"], link["url"]) for link in resume["document"]["header"]["links"]]


def warnings(resume) -> set[str]:
    return {warning["type"] for warning in resume["score"]["after"]["warnings"]}


def test_contact_details_go_on_the_resume_and_clear_the_warnings(client, model):
    user, job = record(github_username="sam")
    before = generate(client, user, job)
    assert {"missing_phone", "missing_linkedin"} <= warnings(before)

    response = patch(client, user, job, {"contact": {"phone": f" {PHONE} ", "linkedin_url": "linkedin.com/in/sam"}})

    assert response.status_code == 200, response.text[:300]
    resume = response.json()["resume"]
    assert resume["document"]["header"]["phone"] == PHONE
    assert links(resume) == [("GitHub", "https://github.com/sam"), ("LinkedIn", LINKEDIN)]
    assert not {"missing_phone", "missing_linkedin"} & warnings(resume)
    assert resume["score"]["after"]["ats_score"] > before["score"]["after"]["ats_score"]
    assert stored(user) == (PHONE, LINKEDIN)


def test_later_resumes_for_any_job_start_with_them(client, model):
    user, job = record()
    generate(client, user, job)
    patch(client, user, job, {"contact": {"phone": PHONE, "linkedin_url": LINKEDIN}})
    other_job = add_job(user, [("Haskell", "haskell")])

    for resume in (generate(client, user, other_job), generate(client, user, job)):
        assert resume["document"]["header"]["phone"] == PHONE
        assert links(resume) == [("LinkedIn", LINKEDIN)]


def test_only_what_is_sent_changes_and_a_blank_removes_it(client, model):
    user, job = record()
    generate(client, user, job)
    patch(client, user, job, {"contact": {"phone": PHONE, "linkedin_url": LINKEDIN}})

    replaced = patch(client, user, job, {"contact": {"linkedin_url": "linkedin.com/in/samr"}}).json()["resume"]
    assert replaced["document"]["header"]["phone"] == PHONE
    assert links(replaced) == [("LinkedIn", "https://www.linkedin.com/in/samr")]

    cleared = patch(client, user, job, {"contact": {"phone": "", "linkedin_url": None}}).json()["resume"]
    assert cleared["document"]["header"]["phone"] is None and links(cleared) == []
    assert stored(user) == (None, None)


def test_a_change_that_says_nothing_about_contact_leaves_it(client, model):
    user, job = record()
    generate(client, user, job)
    patch(client, user, job, {"contact": {"phone": PHONE}})

    resume = patch(client, user, job, {"lines": []}).json()["resume"]

    assert resume["document"]["header"]["phone"] == PHONE
    assert stored(user) == (PHONE, None)


@pytest.mark.parametrize("contact", [
    {"phone": "call me"},
    {"phone": PHONE, "linkedin_url": "javascript:alert(1)"},
    {"linkedin_url": "https://evil.test/in/sam"},
])
def test_a_detail_that_cannot_be_used_saves_nothing(client, model, contact):
    user, job = record()
    generate(client, user, job)

    response = patch(client, user, job, {"contact": contact, "section_order": [
        "skills", "summary", "experience", "projects", "education"]})

    assert response.status_code == 400 and isinstance(response.json()["detail"], str)
    resume = client.get(f"/tailored-resumes/{job}", headers=auth(user.id)).json()["resume"]
    assert resume["document"]["header"]["phone"] is None and links(resume) == []
    assert resume["document"]["section_order"][0] == "summary"
    assert stored(user) == (None, None)


def test_another_user_cannot_set_them(client, model):
    user, job = record()
    generate(client, user, job)
    other = new_user()

    assert patch(client, other, job, {"contact": {"phone": PHONE}}).status_code == 404
    assert stored(other) == stored(user) == (None, None)


def skills(user, job) -> dict[str, str]:
    return {skill.canonical: skill.name for skill in select_(user, job).document.skills}


def test_a_listed_skill_takes_the_jobs_spelling_of_the_same_name(seeded):
    user = new_user()
    item = project(user, "Tool", ["Postgres", "k8s", "version control"])
    for canonical in ("postgres", "kubernetes", "git"):
        evidence(user, canonical, "project", item)
    job = add_job(user, [("PostgreSQL", "postgres"), ("Kubernetes", "kubernetes"), ("Git", "git")])

    # "version control" isn't another spelling of Git, so it stays as written.
    assert skills(user, job) == {"postgres": "PostgreSQL", "kubernetes": "Kubernetes", "git": "version control"}


def test_any_of_the_jobs_wordings_may_be_the_matching_one(seeded):
    user = new_user()
    item = project(user, "Tool", ["k8s"])
    evidence(user, "kubernetes", "project", item)
    job = add_job(user, [("container orchestration", "kubernetes")], nice=[("Kubernetes", "kubernetes")])

    assert skills(user, job) == {"kubernetes": "Kubernetes"}


def test_a_skill_the_job_does_not_ask_for_keeps_the_users_spelling(seeded):
    user = new_user()
    item = project(user, "Tool", ["Postgres"])
    evidence(user, "postgres", "project", item)

    assert skills(user, add_job(user, [("Haskell", "haskell")])) == {"postgres": "Postgres"}
