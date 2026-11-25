"""The sync and upload endpoints keep the evidence record consistent.

Only the outside world is stubbed (the GitHub API, the LLM extraction, the
identity refresh); everything else is the real endpoint code on the real
database.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.facts import Education, Experience, Project, Resume, User
from app.models.github_analysis import GithubProjectAnalysis
from tests.api.test_evidence import add_repo, auth, run


@pytest.fixture
def user_id(seeded):
    async def create(db):
        user = User(name="Fay", email=f"{uuid.uuid4().hex}@example.test", auth_provider="local",
                    target_roles=[], target_companies=[], github_username="fay")
        db.add(user)
        await db.commit()
        return user.id
    return run(create)


@pytest.fixture(autouse=True)
def no_side_effects(monkeypatch):
    """The parts that would reach the network or an LLM."""
    async def nothing(*args, **kwargs):
        return None
    monkeypatch.setattr("app.api.sync.persist_engineering_snapshot", nothing)
    monkeypatch.setattr("app.api.sync.trigger_identity_refresh", nothing)
    monkeypatch.setattr("app.api.resume.trigger_identity_refresh", nothing)


def projects(user_id):
    async def go(db):
        rows = (await db.execute(select(Project).where(Project.user_id == user_id))).scalars().all()
        return sorted((p.name, p.source) for p in rows)
    return run(go)


def evidence_updated_at(user_id):
    async def go(db):
        return (await db.execute(select(User.evidence_updated_at).where(User.id == user_id))).scalar_one()
    return run(go)


def test_github_sync_adds_projects_without_duplicating_on_resync(user_id, client, monkeypatch):
    async def fake_sync(db, user, username, token):
        # What a real sync leaves behind: one analysis row per repo.
        for name in ("alpha", "beta"):
            existing = (await db.execute(select(GithubProjectAnalysis).where(
                GithubProjectAnalysis.user_id == user.id, GithubProjectAnalysis.repo_name == name))).scalar_one_or_none()
            if existing is None:
                db.add(GithubProjectAnalysis(
                    user_id=user.id, repo_name=name, description=f"{name} repo", html_url=f"https://github.com/fay/{name}",
                    category="Backend", technologies=["python"], capabilities=[], computed_at=datetime.now(timezone.utc)))
        await db.commit()
        return {"status": "success"}
    monkeypatch.setattr("app.api.sync.sync_github", fake_sync)
    headers = auth(user_id)
    assert evidence_updated_at(user_id) is None

    first = client.post("/sync/github", headers=headers, json={"username": "fay", "token": "t"})
    assert first.status_code == 200
    assert projects(user_id) == [("alpha", "github"), ("beta", "github")]
    stamped = evidence_updated_at(user_id)
    assert stamped is not None

    second = client.post("/sync/github", headers=headers, json={"username": "fay", "token": "t"})
    assert second.status_code == 200
    assert projects(user_id) == [("alpha", "github"), ("beta", "github")]  # no duplicates
    assert evidence_updated_at(user_id) >= stamped

    shown = client.get("/profile/data", headers=headers).json()["projects"]
    assert sorted(p["name"] for p in shown) == ["alpha", "beta"]


def test_resume_upload_links_projects_and_keeps_earlier_decisions(user_id, client, monkeypatch):
    add_repo(user_id, "polaris-api")
    add_repo(user_id, "side-project")

    uploads = {"count": 0}

    async def fake_ingest(raw_text, db, user, filename=None, pdf_bytes=None):
        uploads["count"] += 1
        resume = Resume(user_id=user.id, raw_text=raw_text, filename=filename)
        db.add(resume)
        await db.flush()
        db.add(Project(user_id=user.id, resume_id=resume.id, name="Polaris API", description="from resume", source="resume"))
        db.add(Project(user_id=user.id, resume_id=resume.id, name="Resume Only", description="from resume", source="resume"))
        db.add(Experience(user_id=user.id, resume_id=resume.id, role="Engineer", company="Acme", source="resume"))
        db.add(Education(user_id=user.id, resume_id=resume.id, institution="State U", degree="BSc", source="resume"))
        await db.commit()
        return {"resume_id": str(resume.id)}

    async def fake_text(raw_bytes):
        return "resume text"
    monkeypatch.setattr("app.api.resume.ingest_resume", fake_ingest)
    monkeypatch.setattr("app.api.resume.extract_text_from_pdf_bytes", fake_text)
    headers = auth(user_id)
    pdf = {"file": ("resume.pdf", b"%PDF-1.4 stub", "application/pdf")}

    assert client.post("/resume/upload", headers=headers, files=pdf).status_code == 200

    # The resume project was linked to its repo; the repo that is not on the resume got its own project.
    assert projects(user_id) == [("Polaris API", "both"), ("Resume Only", "resume"), ("side-project", "github")]
    assert evidence_updated_at(user_id) is not None

    # The user hides one resume project, then uploads a new version of the resume.
    shown = {p["name"]: p for p in client.get("/profile/data", headers=headers).json()["projects"]}
    client.patch(f"/profile/projects/{shown['Resume Only']['id']}", headers=headers, json={"action": "hide"})
    assert client.post("/resume/upload", headers=headers, files=pdf).status_code == 200

    after = {p["name"]: p for p in client.get("/profile/data", headers=headers).json()["projects"]}
    assert after["Resume Only"]["is_hidden"] is True                    # the decision carried over
    assert after["Polaris API"]["sources"] == ["resume", "github"]      # still linked, not duplicated
    assert sorted(after) == ["Polaris API", "Resume Only", "side-project"]
