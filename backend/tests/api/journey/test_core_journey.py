"""The core journey of the problem statement, from a new account to a tailored
resume and an interview kit, through the real routes on the real database. Only
the model, GitHub and LeetCode are stood in for.

    connect sources -> review the profile -> add a job -> see fit and gaps
    -> tailored resume (review, export) and interview kit (practise, progress)
"""
import io
import uuid

import pytest
from docx import Document

from app.services.leetcode import leetcode_sync
from app.services.resume.docx_parser import extract_text_from_docx
from app.services.resume.pdf_parser import extract_text_from_pdf
from tests.api.journey.world import (
    GITHUB_LOGIN,
    JOB_TEXT,
    LINKEDIN_TEXT,
    RESUME_LINES,
    StandInModel,
    leetcode_profile,
    stand_in_github,
)


@pytest.fixture
def world(monkeypatch):
    from app.core import llm

    model = StandInModel()
    monkeypatch.setattr(llm, "API_KEY", "test-key")
    monkeypatch.setattr(llm, "chat_completion", model)
    stand_in_github(monkeypatch.setattr)

    async def profile(username, *args, **kwargs):
        return leetcode_profile()
    monkeypatch.setattr(leetcode_sync, "fetch_leetcode_profile", profile)
    return model


def resume_file() -> bytes:
    document = Document()
    for line in RESUME_LINES:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class Visitor:
    """One person using the app. Every request must succeed."""

    def __init__(self, client):
        self.client, self.headers = client, {}

    def call(self, method, url, **kwargs):
        response = self.client.request(method, url, headers=self.headers, **kwargs)
        assert response.status_code == 200, f"{method} {url} -> {response.status_code}: {response.text[:500]}"
        return response

    def get(self, url):
        return self.call("GET", url).json()

    def post(self, url, body=None, **kwargs):
        return self.call("POST", url, **({"json": body} if body is not None else {}), **kwargs).json()

    def patch(self, url, body):
        return self.call("PATCH", url, json=body).json()


def test_from_a_new_account_to_a_tailored_resume_and_an_interview_kit(client, world):
    me = Visitor(client)
    account = me.post("/auth/register", {
        "first_name": "Priya", "last_name": "Raman", "email": f"{uuid.uuid4().hex}@example.com",
        "password": "a long enough password",
    })
    me.headers = {"Authorization": f"Bearer {account['access_token']}"}

    # --- connect sources ------------------------------------------------------
    me.post("/resume/upload", files={"file": (
        "priya.docx", resume_file(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    me.post("/sync/github", {"username": GITHUB_LOGIN, "token": "stand-in-token"})
    me.post("/sync/leetcode", {"username": GITHUB_LOGIN})
    me.post("/linkedin/ingest", {"raw_text": LINKEDIN_TEXT})

    # --- review the profile ---------------------------------------------------
    profile = me.get("/profile/data")
    projects = {p["name"].lower(): p for p in profile["projects"]}
    assert len(profile["projects"]) == 2, "the resume's project and its repository are one"
    assert set(projects["ledger"]["sources"]) == {"resume", "github"}
    assert projects["campus-map"]["sources"] == ["github"], "a repository the resume leaves out is a candidate"
    roles = {e["title"]: e for e in profile["experiences"]}
    assert set(roles) == {"Backend Intern", "Teaching Assistant"}
    assert roles["Teaching Assistant"]["sources"] == ["linkedin"]
    assert all(item["sources"] for item in [*profile["projects"], *profile["experiences"], *profile["education"]])
    me.patch(f"/profile/projects/{projects['ledger']['id']}", {"action": "confirm"})
    me.patch(f"/profile/projects/{projects['campus-map']['id']}", {"action": "hide"})

    # --- add a job, see fit and gaps ------------------------------------------
    job = me.post("/job-intelligence/analyze", {"raw_text": JOB_TEXT})
    job_id = job["job_intelligence"]["id"]
    fit = me.get(f"/jobs/by-intelligence/{job_id}")["report"]
    met = {entry["skill"]: entry for entry in [*fit["have"], *fit["partial"]]}
    assert "python" in met
    assert all(entry["supporting"] for entry in met.values()), "every met requirement points at evidence"
    missing = {entry["skill"]: entry for entry in fit["missing"]}
    assert (missing["kubernetes"]["severity"], missing["kubernetes"]["supporting"]) == ("critical", [])
    # Used in one job only, which isn't enough to count; the evidence is still shown.
    assert missing["postgres"]["supporting"]

    # --- tailored resume: generate, review, export ----------------------------
    made = me.post(f"/tailored-resumes/{job_id}")["resume"]
    document = made["document"]
    entries = [*document["experience"], *document["projects"], *document["education"]]
    lines = [line for entry in entries for line in entry["bullets"]]
    assert lines and all(line["sources"] for line in lines), "every bullet traces to evidence"
    assert all(skill["sources"] for skill in document["skills"])
    assert "campus-map" not in str(document).lower(), "a hidden project stays off"
    suggested = [line for line in lines if line["rewrite"]]
    assert suggested and all(line["text"] == line["original"] for line in suggested), "nothing unapproved appears"
    chosen = suggested[0]
    assert chosen["flags"], "new wording has to be confirmed"
    changed = me.patch(f"/tailored-resumes/{job_id}/versions/{made['version']}", {
        "lines": [{"line_id": chosen["id"], "decision": "accepted", "confirm_flags": True}]})["resume"]
    assert chosen["rewrite"] in str(changed["document"])
    for file_format, read in (("pdf", extract_text_from_pdf), ("docx", extract_text_from_docx)):
        exported = me.call("GET", f"/tailored-resumes/{job_id}/versions/{made['version']}/export?format={file_format}")
        text = " ".join(read(io.BytesIO(exported.content)).split())
        assert "Priya Raman" in text and chosen["rewrite"] in text

    # --- interview kit: categories, evidence, practice, progress --------------
    assert me.get(f"/interview/kits/{job_id}")["kit"] is None
    kit = me.post(f"/interview/kits/{job_id}")["kit"]
    assert {q["category"] for q in kit["questions"]} == {
        "technical_depth", "system_design", "behavioral", "role_specific"}
    assert kit["notice"] is None and kit["evidence_notice"] is None and kit["stale"] is False
    for question in kit["questions"]:
        # Tied to specific evidence, or an explicit gap.
        assert question["thin"] is (question["outline"]["story"] is None), question["topic"]
        assert question["thin"] or question["shows"] or question["outline"]["story"]["title"]
    assert any(not q["thin"] for q in kit["questions"]) and any(q["thin"] for q in kit["questions"])
    answered = next(q for q in kit["questions"] if q["topic"] == "PostgreSQL")
    assert answered["outline"]["story"]["title"] == "Backend Intern at Northwind"
    assert answered["shows"] == ["PostgreSQL"]

    attempt = me.post(f"/interview/questions/{answered['id']}/attempts", {
        "answer": "At Northwind I cut p95 latency from 800ms to 210ms by adding indexes to PostgreSQL."})
    assert attempt["score"] is not None and attempt["score"] > 0
    assert attempt["feedback"]["warnings"] == []
    progress = me.get(f"/interview/kits/{job_id}/progress")
    assert (progress["practised"], progress["total"]) == (1, len(kit["questions"]))
    assert progress["weakest"] is not None
    assert me.get(f"/interview/kits/{job_id}")["kit"]["practised"] == 1
    again = me.post(f"/interview/kits/{job_id}/versions/{kit['version']}/evidence")["kit"]
    assert [q["id"] for q in again["questions"]] == [q["id"] for q in kit["questions"]]

    # --- study plan and career plan -------------------------------------------
    study = me.get(f"/interview/study-plan/{job_id}")
    gaps = {gap["skill"]: gap for gap in study["gaps"]}
    assert "kubernetes" in gaps and gaps["kubernetes"]["questions"]
    goal = me.post("/goals", {"title": "Backend interview", "job_intelligence_id": job_id})
    plan = me.post(f"/goals/{goal['id']}/plan")
    assert plan["degraded"] is False and plan["daily_plan"]
    assert {g["skill"] for g in plan["study_plan"]["gaps"]} == set(gaps)

    # Every part that needs the model got an answer it could use.
    assert world.answered >= {
        "resume_extraction", "linkedin_extraction", "job_extraction", "bullet_rewrite", "kit_questions",
        "practice_review", "career_plan",
    }, world.answered
