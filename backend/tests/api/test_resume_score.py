"""The tailored resume's score beside the uploaded one's, through the API. Real
database; stand-in model.
"""
import uuid
from datetime import date

import pytest

from app.core import llm
from app.models.facts import Resume
from app.models.inference import ResumeAnalysis
from app.schemas.resume.tailored import TailoredResumeDocument
from app.services.resume.tailored_score import plain_text
from tests.api.test_evidence import auth, run
from tests.api.test_resume_rewriting import DOCKER, KUBERNETES, POSTGRES, add_job
from tests.api.test_resume_selection import NOW, add, experience, new_user, upload
from tests.llm_stub import model  # noqa: F401 (model is a fixture)

UPLOADED = """Sam Rivera
sam@example.test | +1 555 123 4567 | github.com/sam

Experience
Engineer, Acme
- Tuned Postgres queries.

Education
State University

Skills
Docker
"""


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "test-key")


def generate(client, user, job):
    response = client.post(f"/tailored-resumes/{job}", headers=auth(user.id))
    assert response.status_code == 200, response.text[:300]
    return response.json()


def made(client, model, *, uploaded=UPLOADED, required=(POSTGRES, KUBERNETES), nice=(DOCKER,)):
    """A user with an uploaded resume (unless None) and a generated tailored one."""
    user = new_user()
    resume = None
    if uploaded is not None:
        resume = add(Resume(user_id=user.id, raw_text=uploaded, filename="sam.pdf", created_at=NOW))
    experience(user, "Engineer", bullets=["Tuned Postgres queries."], resume_id=resume)
    job = add_job(user, list(required), nice=list(nice))
    if any(raw == "PostgreSQL" for raw, _canonical in required):
        model.will({"rewrite": "Tuned PostgreSQL queries."})
    return user, job, generate(client, user, job)


def test_both_resumes_are_scored_for_the_job(client, model):
    _user, _job, view = made(client, model)

    score = view["resume"]["score"]

    assert score["uploaded"]["filename"] == "sam.pdf"
    for card in (score["before"], score["after"]):
        assert 0 < card["ats_score"] <= 100
        assert set(card["parts"]) == {
            "parsing", "completeness", "content_quality", "structure", "keywords", "professionalism"}
        # Required and implied skills only: "docker" is merely nice to have.
        assert card["keywords"]["total"] == 2
    # The job writes "PostgreSQL"; neither resume does yet.
    assert score["before"]["keywords"]["missing"] == ["kubernetes", "postgresql"]


def test_an_accepted_suggestion_counts_and_a_pending_one_does_not(client, model):
    user, job, view = made(client, model)
    pending = view["resume"]["score"]["after"]["keywords"]
    assert (pending["matched"], pending["percentage"]) == ([], 0)

    line = view["resume"]["document"]["experience"][0]["bullets"][0]
    accepted = client.patch(
        f"/tailored-resumes/{job}/versions/1", headers=auth(user.id),
        json={"lines": [{"line_id": line["id"], "decision": "accepted"}]},
    ).json()["resume"]["score"]

    assert accepted["after"]["keywords"] == {
        "matched": ["postgresql"], "missing": ["kubernetes"], "total": 2, "percentage": 50}
    assert accepted["before"] == view["resume"]["score"]["before"]


def test_contact_details_missing_from_the_tailored_resume_are_warned_of(client, model):
    _user, _job, view = made(client, model)
    score = view["resume"]["score"]

    def warned(card):
        return {warning["type"] for warning in card["warnings"]}

    assert "missing_phone" not in warned(score["before"])
    assert "missing_phone" in warned(score["after"])  # the header has none
    assert "missing_email" not in warned(score["after"])


def test_without_an_upload_there_is_only_the_tailored_score(client, model):
    _user, _job, view = made(client, model, uploaded=None)

    score = view["resume"]["score"]

    assert score["before"] is None and score["uploaded"] is None
    assert score["after"]["ats_score"] > 0


def test_the_latest_upload_is_the_one_compared(client, model):
    user, job, _view = made(client, model)
    upload(user, days_ago=30)
    add(Resume(user_id=user.id, raw_text="Kubernetes", filename="newer.pdf", created_at=NOW.replace(year=NOW.year + 1)))

    score = client.get(f"/tailored-resumes/{job}", headers=auth(user.id)).json()["resume"]["score"]

    assert score["uploaded"]["filename"] == "newer.pdf"
    assert score["before"]["keywords"]["matched"] == ["kubernetes"]


def test_a_job_that_lists_no_skills_has_no_keyword_score(client, model):
    _user, _job, view = made(client, model, required=(), nice=(DOCKER,))

    score = view["resume"]["score"]

    assert score["before"]["keywords"] is None and score["after"]["keywords"] is None


def test_scoring_asks_nothing_of_the_model_and_saves_no_analysis(client, model):
    user, job, _view = made(client, model)
    asked = len(model.requests)

    assert client.get(f"/tailored-resumes/{job}", headers=auth(user.id)).status_code == 200

    async def analyses(db):
        from sqlalchemy import func, select
        return await db.scalar(select(func.count()).select_from(ResumeAnalysis)
                               .where(ResumeAnalysis.user_id == user.id))
    assert len(model.requests) == asked
    assert run(analyses) == 0


# --- The text that is scored ---------------------------------------------------

def source(kind="experience") -> dict:
    return {"kind": kind, "id": str(uuid.uuid4())}


def line(text, **fields) -> dict:
    return {"original": text, "sources": [source()], **fields}


def test_the_text_holds_what_is_on_the_resume_in_its_order():
    document = TailoredResumeDocument(
        header={"full_name": "Sam Rivera", "email": "s@x.test", "links": [{"label": "GitHub", "url": "https://github.com/sam"}]},
        summary={"rewrite": "Not yet approved.", "sources": [source()]},
        experience=[{"role": "Engineer", "company": "Acme", "start_date": date(2022, 3, 1), "end_date_text": "Present",
                     "bullets": [line("Old wording.", rewrite="Pending wording."),
                                 line("Replaced.", edited="My wording.")], "sources": [source()]}],
        projects=[{"name": "Ledger", "technologies": ["Python", "Redis"], "bullets": [], "sources": [source("project")]}],
        education=[{"institution": "State", "degree": "BSc", "start_date_text": "2019", "is_current": True,
                    "sources": [source("education")]}],
        skills=[{"name": "Python", "canonical": "python", "sources": [source()]}],
        section_order=["summary", "skills", "experience", "projects", "education"],
    )

    assert plain_text(document) == "\n".join([
        "Sam Rivera",
        "s@x.test | https://github.com/sam",
        "", "Skills", "Python",
        "", "Experience", "Engineer, Acme", "Mar 2022 - Present", "- Old wording.", "- My wording.",
        "", "Projects", "Ledger", "Python, Redis",
        "", "Education", "State", "BSc", "2019 - Present",
    ])


def test_an_empty_resume_is_just_the_name():
    assert plain_text(TailoredResumeDocument(header={"full_name": "Sam Rivera"})) == "Sam Rivera\n"
