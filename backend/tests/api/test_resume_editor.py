"""The tailored resume editor, through the API. Real database; stand-in model."""
import uuid
from datetime import datetime, timezone

import pytest
from openai import RateLimitError

from app.core import llm, llm_budget
from app.models.facts import Experience, Project, User
from tests.api.test_evidence import auth, run
from tests.api.test_resume_rewriting import POSTGRES, add_job
from tests.api.test_resume_selection import evidence, experience, new_user, project, repo
from tests.api.test_resume_sources import change
from tests.llm_stub import api_error, model  # noqa: F401 (model is a fixture)

ORIGINALS = ["Tuned Postgres queries.", "Backed up Postgres."]


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "test-key")


def record():
    user = new_user()
    role = experience(user, "Engineer", bullets=ORIGINALS)
    return user, add_job(user, [POSTGRES]), role


@pytest.fixture
def made(client, model):
    """A generated resume: the first rewrite is clean, the second flagged."""
    user, job, role = record()
    model.will({"rewrite": "Tuned PostgreSQL queries."}, {"rewrite": "Backed up PostgreSQL and Redis."})
    response = client.post(f"/tailored-resumes/{job}", headers=auth(user.id))
    assert response.status_code == 200, response.text[:300]
    return user, job, role, response.json()


def lines(view) -> list[dict]:
    return view["resume"]["document"]["experience"][0]["bullets"]


def read(client, user, job, query=""):
    return client.get(f"/tailored-resumes/{job}{query}", headers=auth(user.id))


def patch(client, user, job, body, version=1):
    return client.patch(f"/tailored-resumes/{job}/versions/{version}", json=body, headers=auth(user.id))


def decide(client, user, job, line, **fields):
    return patch(client, user, job, {"lines": [{"line_id": line["id"], **fields}]})


def test_nothing_is_there_until_a_resume_is_generated(client, seeded):
    user, job, _role = record()

    view = read(client, user, job).json()

    assert view == {"job": {"id": job, "role": "Backend Engineer", "company": "Globex"},
                    "versions": [], "resume": None}


def test_generating_saves_a_version_with_suggestions_not_yet_applied(client, made):
    user, job, role, view = made

    assert view["versions"] == [1]
    assert view["resume"]["version"] == 1 and view["resume"]["stale"] is False
    clean, flagged = lines(view)
    assert (clean["text"], clean["rewrite"], clean["decision"], clean["flags"]) == (
        ORIGINALS[0], "Tuned PostgreSQL queries.", "pending", [])
    assert flagged["flags"] and flagged["text"] == ORIGINALS[1]
    assert read(client, user, job).json() == view


def test_each_line_comes_with_its_evidence(client, made):
    _user, _job, role, view = made

    cited = view["resume"]["evidence"][f"experience:{role}:1"]

    assert cited == {"kind": "experience", "title": "Engineer at Acme", "origin": "Resume",
                     "detail": ORIGINALS[1], "url": None, "available": True}
    document = view["resume"]["document"]
    items = [*document["experience"], *document["skills"], *lines(view)]
    for ref in (ref for item in items for ref in item["sources"]):
        key = f"{ref['kind']}:{ref['id'] or ''}:{'' if ref['bullet'] is None else ref['bullet']}"
        assert key in view["resume"]["evidence"], key


def test_evidence_covers_projects_repos_and_practice(client, model, seeded):
    user = new_user()
    tool = project(user, "infra", ["Postgres"], "Runs Postgres.", source="github", github_repo_name="infra",
                   repo_url="https://github.com/sam/infra")
    analysis = repo(user, "infra", ["Postgres"])
    evidence(user, "postgres", "github_repo", analysis)
    evidence(user, "algorithms", "leetcode_tag", None)
    job = add_job(user, [POSTGRES, ("Algorithms", "algorithms")])
    model.will({"rewrite": "Runs PostgreSQL."})

    view = client.post(f"/tailored-resumes/{job}", headers=auth(user.id)).json()
    found = view["resume"]["evidence"]

    assert found[f"project:{tool}:"]["origin"] == "GitHub"
    assert found[f"project:{tool}:0"]["detail"] == "Runs Postgres."
    assert found[f"github_repo:{analysis}:"]["detail"] == "Found in the repository: Postgres"
    assert found["leetcode_tag::"]["origin"] == "LeetCode"


def test_a_clean_rewrite_is_accepted_and_appears_on_the_resume(client, made):
    user, job, _role, view = made

    response = decide(client, user, job, lines(view)[0], decision="accepted")

    assert response.status_code == 200, response.text[:300]
    assert lines(response.json())[0]["text"] == "Tuned PostgreSQL queries."
    assert lines(read(client, user, job).json())[0]["decision"] == "accepted"


def test_a_flagged_rewrite_needs_confirmation(client, made):
    user, job, _role, view = made
    flagged = lines(view)[1]

    refused = decide(client, user, job, flagged, decision="accepted")

    assert refused.status_code == 409 and "Confirm" in refused.json()["detail"]
    assert lines(read(client, user, job).json())[1]["decision"] == "pending"

    confirmed = decide(client, user, job, flagged, decision="accepted", confirm_flags=True)
    after = lines(confirmed.json())[1]
    assert after["text"] == "Backed up PostgreSQL and Redis."
    assert after["flags"]  # the warning stays on record


def test_rejecting_and_undoing(client, made):
    user, job, _role, view = made
    clean = lines(view)[0]
    decide(client, user, job, clean, decision="accepted")

    rejected = decide(client, user, job, clean, decision="rejected").json()
    assert (lines(rejected)[0]["text"], lines(rejected)[0]["decision"]) == (ORIGINALS[0], "rejected")

    undone = decide(client, user, job, clean, decision="pending").json()
    assert lines(undone)[0]["decision"] == "pending"


def test_the_users_own_wording_wins_until_removed(client, made):
    user, job, _role, view = made
    clean = lines(view)[0]

    edited = decide(client, user, job, clean, edited="  Cut 40 slow\nqueries. ").json()
    assert (lines(edited)[0]["text"], lines(edited)[0]["edited"]) == ("Cut 40 slow queries.", "Cut 40 slow queries.")

    # A change that doesn't mention the edit leaves it.
    kept = decide(client, user, job, clean, decision="rejected").json()
    assert lines(kept)[0]["edited"] == "Cut 40 slow queries."

    removed = decide(client, user, job, clean, edited="   ").json()
    assert (lines(removed)[0]["text"], lines(removed)[0]["edited"]) == (ORIGINALS[0], None)


def test_sections_can_be_reordered(client, made):
    user, job, _role, _view = made
    order = ["summary", "skills", "experience", "projects", "education"]

    response = patch(client, user, job, {"section_order": order})

    assert response.status_code == 200, response.text[:300]
    assert read(client, user, job).json()["resume"]["document"]["section_order"] == order


@pytest.mark.parametrize(("body", "status"), [
    ({"section_order": ["skills"]}, 400),
    ({"section_order": ["skills"] * 5}, 400),
    ({"section_order": ["hobbies"]}, 422),
    ({"lines": [{"line_id": "nope", "decision": "accepted"}]}, 400),
    ({"lines": [{"line_id": "{first}", "edited": "x" * 2001}]}, 422),
    ({"lines": [{"line_id": "{first}", "decision": "maybe"}]}, 422),
])
def test_an_impossible_change_is_refused(client, made, body, status):
    user, job, _role, view = made
    for change_ in body.get("lines", []):
        change_["line_id"] = change_["line_id"].replace("{first}", lines(view)[0]["id"])

    assert patch(client, user, job, body).status_code == status
    assert read(client, user, job).json() == view


def test_changes_are_saved_all_or_none(client, made):
    user, job, _role, view = made
    clean, flagged = lines(view)

    response = patch(client, user, job, {
        "lines": [{"line_id": clean["id"], "decision": "accepted"},
                  {"line_id": flagged["id"], "decision": "accepted"}],  # not confirmed
        "section_order": ["skills", "summary", "experience", "projects", "education"],
    })

    assert response.status_code == 409
    assert read(client, user, job).json() == view


def test_what_the_browser_sends_cannot_alter_the_evidence(client, made):
    user, job, _role, view = made
    flagged = lines(view)[1]

    response = decide(client, user, job, flagged, decision="rejected", flags=[], original="Led a team.",
                      rewrite="Led a team.", sources=[])

    after = lines(response.json())[1]
    assert {key: after[key] for key in ("original", "rewrite", "flags", "sources")} == {
        key: flagged[key] for key in ("original", "rewrite", "flags", "sources")}


def test_there_is_nothing_to_accept_without_a_rewrite(client, model, seeded):
    user, job, _role = record()
    model.will(api_error(RateLimitError, 429))
    view = client.post(f"/tailored-resumes/{job}", headers=auth(user.id)).json()

    response = decide(client, user, job, lines(view)[0], decision="accepted")

    assert response.status_code == 400
    assert "usage limit" in view["resume"]["document"]["notice"]


def test_generating_again_keeps_earlier_versions_and_their_choices(client, made, model):
    user, job, _role, view = made
    decide(client, user, job, lines(view)[0], decision="accepted")
    model.will({"rewrite": "Tuned PostgreSQL queries."}, {"rewrite": "Backed up PostgreSQL."})

    second = client.post(f"/tailored-resumes/{job}", headers=auth(user.id)).json()

    assert second["versions"] == [2, 1] and second["resume"]["version"] == 2
    assert lines(second)[0]["decision"] == "pending"
    first = read(client, user, job, "?version=1").json()
    assert first["resume"]["version"] == 1 and lines(first)[0]["decision"] == "accepted"
    assert read(client, user, job, "?version=3").status_code == 404
    assert patch(client, user, job, {}, version=3).status_code == 404


def test_a_change_of_evidence_is_shown(client, made):
    user, job, role, _view = made
    change(User, user.id, evidence_updated_at=datetime.now(timezone.utc))
    change(Experience, role, bullets=["Reworded since."])

    resume = read(client, user, job).json()["resume"]

    assert resume["stale"] is True
    assert resume["evidence"][f"experience:{role}:0"]["detail"] == "Reworded since."
    assert resume["evidence"][f"experience:{role}:1"]["detail"] is None  # that bullet is gone

    change(Experience, role, is_hidden=True)
    hidden = read(client, user, job).json()["resume"]["evidence"][f"experience:{role}:0"]
    assert (hidden["available"], hidden["title"], hidden["detail"]) == (False, "Removed or hidden item", None)


def test_another_user_cannot_read_or_change_a_resume(client, made):
    _user, job, _role, view = made
    other = new_user()

    assert read(client, other, job).status_code == 404
    assert read(client, other, job, "?version=1").status_code == 404
    assert patch(client, other, job, {"lines": [{"line_id": lines(view)[0]["id"], "decision": "accepted"}]}
                 ).status_code == 404


def test_a_user_out_of_calls_can_still_generate(client, model, monkeypatch, seeded):
    user, job, _role = record()
    monkeypatch.setattr(llm_budget, "DAILY_CALLS", 1)

    async def spend():
        assert await llm_budget.reserve(user.id)
    import asyncio
    asyncio.run(spend())

    response = client.post(f"/tailored-resumes/{job}", headers=auth(user.id))

    assert response.status_code == 200, response.text[:300]
    document = response.json()["resume"]["document"]
    assert "today's limit" in document["notice"]
    assert model.requests == []
