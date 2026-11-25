"""The unified evidence record: GitHub projects, reviews, carry-over,
hiding, and staleness of cached reports.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import create_access_token
from app.models.facts import Education, Experience, Project, Resume, User
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import ProjectClaimAuditReview
from app.services.evidence.review import carry_over_reviews, dedupe_visible
from app.services.evidence.state import evidence_cutoff, touch_evidence
from app.services.projects.claim_audit_llm import get_cached_claim_audit_report
from app.services.projects.linking import link_project, unlink_project
from app.services.projects.reconcile import reconcile_projects
from tests.api.conftest import _new_engine


def run(fn):
    """Runs `fn(db)` in its own session and event loop and returns its result."""
    async def go():
        engine = _new_engine()
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with factory() as db:
                return await fn(db)
        finally:
            await engine.dispose()
    return asyncio.run(go())


@pytest.fixture
def user_id(seeded):
    """A brand-new user per test, so tests cannot affect each other."""
    async def create(db):
        user = User(name="Eve", email=f"{uuid.uuid4().hex}@example.test", auth_provider="local",
                    target_roles=[], target_companies=[])
        db.add(user)
        await db.commit()
        return user.id
    return run(create)


def add_repo(user_id, name, *, fork=False, meaningful=False, description="desc", technologies=("python",)):
    async def go(db):
        db.add(GithubProjectAnalysis(
            user_id=user_id, repo_name=name, description=description, html_url=f"https://github.com/e/{name}",
            category="Backend", technologies=list(technologies), capabilities=[],
            is_fork=fork, is_meaningful_fork_contribution=meaningful, computed_at=datetime.now(timezone.utc),
        ))
        await db.commit()
    run(go)


def remove_repo(user_id, name):
    async def go(db):
        row = (await db.execute(select(GithubProjectAnalysis).where(
            GithubProjectAnalysis.user_id == user_id, GithubProjectAnalysis.repo_name == name))).scalar_one()
        await db.delete(row)
        await db.commit()
    run(go)


def add_resume_project(user_id, name, *, resume_id=None, **kwargs):
    async def go(db):
        rid = resume_id
        if rid is None:
            resume = Resume(user_id=user_id, raw_text="r")
            db.add(resume)
            await db.flush()
            rid = resume.id
        project = Project(user_id=user_id, resume_id=rid, name=name, stack=["python"], description="d", **kwargs)
        db.add(project)
        await db.commit()
        return project.id
    return run(go)


def projects_of(user_id):
    async def go(db):
        rows = (await db.execute(select(Project).where(Project.user_id == user_id)
                                 .order_by(Project.created_at))).scalars().all()
        return [
            {"id": p.id, "name": p.name, "source": p.source, "repo": p.github_repo_name,
             "status": p.repo_link_status, "review": p.review_state, "hidden": p.is_hidden,
             "resume_id": p.resume_id, "description": p.description}
            for p in rows
        ]
    return run(go)


def reconcile(user_id):
    return run(lambda db: reconcile_projects(db, user_id))


# --------------------------------------------------------------- GitHub projects

def test_a_repo_missing_from_the_resume_becomes_a_project(user_id):
    add_repo(user_id, "side-project", description="A tool I built")

    result = reconcile(user_id)

    assert result.created == 1
    [project] = projects_of(user_id)
    assert (project["name"], project["source"], project["repo"]) == ("side-project", "github", "side-project")
    assert project["resume_id"] is None and project["description"] == "A tool I built"


def test_an_exact_match_is_linked_not_duplicated(user_id):
    add_repo(user_id, "polaris-api")
    add_resume_project(user_id, "Polaris API")

    result = reconcile(user_id)

    assert result.auto_linked == 1 and result.created == 0
    [project] = projects_of(user_id)
    assert (project["source"], project["repo"], project["status"]) == ("both", "polaris-api", "auto")


def test_reconciling_twice_changes_nothing(user_id):
    add_repo(user_id, "alpha")
    add_repo(user_id, "beta")
    add_resume_project(user_id, "Beta")
    reconcile(user_id)
    before = projects_of(user_id)

    second = reconcile(user_id)

    assert not second.changed
    assert projects_of(user_id) == before
    assert len(before) == 2


def test_forks_count_only_with_a_meaningful_contribution(user_id):
    add_repo(user_id, "plain-fork", fork=True)
    add_repo(user_id, "contributed-fork", fork=True, meaningful=True)

    reconcile(user_id)

    assert [p["name"] for p in projects_of(user_id)] == ["contributed-fork"]


def test_a_fuzzy_match_is_left_for_the_user_to_confirm(user_id):
    add_repo(user_id, "cortex-route-gateway")
    project_id = add_resume_project(user_id, "Cortex Route")

    reconcile(user_id)

    by_name = {p["name"]: p for p in projects_of(user_id)}
    assert by_name["Cortex Route"]["repo"] is None            # not auto-linked
    assert by_name["cortex-route-gateway"]["source"] == "github"  # repo still shows up on its own

    # Confirming the link merges the two into one project.
    run(lambda db: link_project(db, user_id, project_id, "cortex-route-gateway"))
    [merged] = projects_of(user_id)
    assert (merged["name"], merged["source"], merged["repo"]) == ("Cortex Route", "both", "cortex-route-gateway")


def test_unlinking_gives_the_repo_its_own_project_and_stays_unlinked(user_id):
    add_repo(user_id, "polaris-api")
    project_id = add_resume_project(user_id, "Polaris API")
    reconcile(user_id)

    run(lambda db: unlink_project(db, user_id, project_id))
    reconcile(user_id)  # a later sync must not silently re-link what the user removed

    by_source = {p["source"]: p for p in projects_of(user_id)}
    assert by_source["resume"]["repo"] is None and by_source["resume"]["status"] == "rejected"
    assert by_source["github"]["name"] == "polaris-api"


def test_sync_refreshes_untouched_github_projects_but_not_reviewed_ones(user_id, client):
    add_repo(user_id, "tool-a", description="old")
    add_repo(user_id, "tool-b", description="old")
    reconcile(user_id)
    headers = {"Authorization": f"Bearer {create_access_token(str(user_id))}"}
    tool_b = next(p for p in projects_of(user_id) if p["name"] == "tool-b")
    edited = client.patch(f"/profile/projects/{tool_b['id']}", headers=headers,
                          json={"action": "edit", "fields": {"description": "my own words"}})
    assert edited.status_code == 200

    async def resync(db):
        for row in (await db.execute(select(GithubProjectAnalysis).where(
                GithubProjectAnalysis.user_id == user_id))).scalars().all():
            row.description = "new from github"
        await db.commit()
    run(resync)
    reconcile(user_id)

    descriptions = {p["name"]: p["description"] for p in projects_of(user_id)}
    assert descriptions == {"tool-a": "new from github", "tool-b": "my own words"}


def test_a_repo_removed_from_github_removes_its_untouched_project_only(user_id, client):
    add_repo(user_id, "gone-auto")
    add_repo(user_id, "gone-reviewed")
    reconcile(user_id)
    headers = {"Authorization": f"Bearer {create_access_token(str(user_id))}"}
    reviewed = next(p for p in projects_of(user_id) if p["name"] == "gone-reviewed")
    client.patch(f"/profile/projects/{reviewed['id']}", headers=headers, json={"action": "confirm"})

    remove_repo(user_id, "gone-auto")
    remove_repo(user_id, "gone-reviewed")
    reconcile(user_id)

    assert [p["name"] for p in projects_of(user_id)] == ["gone-reviewed"]


# ------------------------------------------------------------- review and hiding

def auth(user_id):
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


def test_the_evidence_record_shows_where_each_item_came_from(user_id, client):
    add_repo(user_id, "github-only")
    add_repo(user_id, "shared-project")
    add_resume_project(user_id, "Shared Project")
    add_resume_project(user_id, "Resume Only")
    reconcile(user_id)

    data = client.get("/profile/data", headers=auth(user_id)).json()

    sources = {p["name"]: p["sources"] for p in data["projects"]}
    assert sources == {
        "github-only": ["github"],
        "Shared Project": ["resume", "github"],
        "Resume Only": ["resume"],
    }
    assert all(p["review_state"] == "auto" and p["is_hidden"] is False for p in data["projects"])


def test_hiding_an_item_removes_it_everywhere_but_keeps_it_restorable(user_id, client):
    add_resume_project(user_id, "Keep Me")
    hide_id = add_resume_project(user_id, "Hide Me")

    response = client.patch(f"/profile/projects/{hide_id}", headers=auth(user_id), json={"action": "hide"})
    assert response.status_code == 200 and response.json()["is_hidden"] is True

    listed = {p["name"]: p["is_hidden"] for p in client.get("/profile/data", headers=auth(user_id)).json()["projects"]}
    assert listed == {"Keep Me": False, "Hide Me": True}  # still listed so it can be restored

    async def visible(db):
        rows = (await db.execute(select(Project).where(Project.user_id == user_id)
                                 .order_by(Project.created_at.desc()))).scalars().all()
        return [p.name for p in dedupe_visible("projects", list(rows))]
    assert run(visible) == ["Keep Me"]  # what every other feature reads

    client.patch(f"/profile/projects/{hide_id}", headers=auth(user_id), json={"action": "unhide"})
    assert run(visible) == ["Hide Me", "Keep Me"]


def test_hiding_the_newest_copy_does_not_resurrect_an_older_upload(user_id):
    async def setup(db):
        old_resume, new_resume = Resume(user_id=user_id, raw_text="old"), Resume(user_id=user_id, raw_text="new")
        db.add_all([old_resume, new_resume])
        await db.flush()
        now = datetime.now(timezone.utc)
        db.add(Project(user_id=user_id, resume_id=old_resume.id, name="Widget", created_at=now - timedelta(days=5)))
        db.add(Project(user_id=user_id, resume_id=new_resume.id, name="Widget", created_at=now, is_hidden=True))
        await db.commit()
        rows = (await db.execute(select(Project).where(Project.user_id == user_id)
                                 .order_by(Project.created_at.desc()))).scalars().all()
        return dedupe_visible("projects", list(rows))
    assert run(setup) == []


def test_editing_validates_the_fields(user_id, client):
    project_id = add_resume_project(user_id, "Editable")
    headers = auth(user_id)

    assert client.patch(f"/profile/projects/{project_id}", headers=headers,
                        json={"action": "edit", "fields": {"is_hidden": True}}).status_code == 400
    assert client.patch(f"/profile/projects/{project_id}", headers=headers,
                        json={"action": "edit", "fields": {"name": "  "}}).status_code == 400
    assert client.patch(f"/profile/projects/{project_id}", headers=headers,
                        json={"action": "edit", "fields": {"stack": "python"}}).status_code == 400
    assert client.patch(f"/profile/projects/{project_id}", headers=headers,
                        json={"action": "edit"}).status_code == 400
    assert client.patch(f"/profile/nonsense/{project_id}", headers=headers,
                        json={"action": "hide"}).status_code == 404
    ok = client.patch(f"/profile/projects/{project_id}", headers=headers,
                      json={"action": "edit", "fields": {"name": "Renamed", "stack": ["go", " rust "]}})
    assert ok.status_code == 200
    assert ok.json()["name"] == "Renamed" and ok.json()["skills_used"] == ["go", "rust"]
    assert ok.json()["review_state"] == "edited"


def test_a_hidden_skill_leaves_the_confidence_map_and_comes_back(user_id, client):
    from app.models.inference import SkillEvidence
    from app.models.structure import Skill

    async def give_skill(db):
        skill = Skill(name="elixir", canonical_name=f"elixir-{uuid.uuid4().hex[:6]}", category="language")
        db.add(skill)
        await db.flush()
        db.add(SkillEvidence(user_id=user_id, skill_id=skill.id, source_type="leetcode_tag", weight=0.1,
                             created_at=datetime.now(timezone.utc)))
        await db.commit()
        return skill.canonical_name
    name = run(give_skill)
    headers = auth(user_id)

    def skills():
        return {s["skill"]: s["is_hidden"] for s in client.get("/profile/data", headers=headers).json()["skills"]}

    assert skills() == {name: False}
    assert client.put(f"/profile/skills/{name}/visibility", headers=headers, json={"hidden": True}).status_code == 200
    assert skills() == {name: True}
    client.put(f"/profile/skills/{name}/visibility", headers=headers, json={"hidden": False})
    assert skills() == {name: False}
    assert client.put("/profile/skills/no-such-skill/visibility", headers=headers,
                      json={"hidden": True}).status_code == 404


def test_one_users_hidden_skill_does_not_affect_another(user_id, seeded, client):
    from app.models.inference import SkillEvidence
    from app.models.structure import Skill

    async def give_both(db):
        skill = Skill(name="zig", canonical_name=f"zig-{uuid.uuid4().hex[:6]}", category="language")
        db.add(skill)
        await db.flush()
        for uid in (user_id, seeded["alice_id"]):
            db.add(SkillEvidence(user_id=uid, skill_id=skill.id, source_type="leetcode_tag", weight=0.1,
                                 created_at=datetime.now(timezone.utc)))
        await db.commit()
        return skill.canonical_name
    name = run(give_both)

    client.put(f"/profile/skills/{name}/visibility", headers=auth(user_id), json={"hidden": True})

    alice = client.get("/profile/data", headers=auth(seeded["alice_id"])).json()["skills"]
    assert {s["skill"]: s["is_hidden"] for s in alice}[name] is False


# ------------------------------------------------------------ re-upload carry-over

def test_a_reupload_keeps_what_the_user_decided(user_id, client):
    old_project = add_resume_project(user_id, "Kept")
    hidden_project = add_resume_project(user_id, "Dropped")
    renamed_project = add_resume_project(user_id, "Original Name")
    headers = auth(user_id)
    client.patch(f"/profile/projects/{old_project}", headers=headers, json={"action": "confirm"})
    client.patch(f"/profile/projects/{hidden_project}", headers=headers, json={"action": "hide"})
    client.patch(f"/profile/projects/{renamed_project}", headers=headers,
                 json={"action": "edit", "fields": {"name": "My Better Name", "description": "mine"}})

    async def reupload(db):
        resume = Resume(user_id=user_id, raw_text="second upload")
        db.add(resume)
        await db.flush()
        for name in ("Kept", "Dropped", "Original Name", "Brand New"):
            db.add(Project(user_id=user_id, resume_id=resume.id, name=name, description="from resume"))
        await db.commit()
        carried = await carry_over_reviews(db, user_id, resume.id)
        rows = (await db.execute(select(Project).where(Project.resume_id == resume.id))).scalars().all()
        return carried, {p.name: (p.review_state, p.is_hidden, p.description) for p in rows}

    carried, new_rows = run(reupload)

    assert carried == 3
    assert new_rows["Kept"] == ("confirmed", False, "from resume")
    assert new_rows["Dropped"][1] is True
    assert new_rows["My Better Name"] == ("edited", False, "mine")   # the user's rename and text win
    assert new_rows["Brand New"] == ("auto", False, "from resume")

    # And what every feature now reads: the renamed, edited version, with the dropped one gone.
    async def visible(db):
        rows = (await db.execute(select(Project).where(Project.user_id == user_id)
                                 .order_by(Project.created_at.desc(), Project.id))).scalars().all()
        return sorted(p.name for p in dedupe_visible("projects", list(rows)))
    assert run(visible) == ["Brand New", "Kept", "My Better Name"]


def test_experiences_and_education_are_carried_over_too(user_id, client):
    async def first_upload(db):
        resume = Resume(user_id=user_id, raw_text="one")
        db.add(resume)
        await db.flush()
        exp = Experience(user_id=user_id, resume_id=resume.id, role="Engineer", company="Acme", bullets=["a"])
        edu = Education(user_id=user_id, resume_id=resume.id, institution="State U", degree="BSc")
        db.add_all([exp, edu])
        await db.commit()
        return exp.id, edu.id
    exp_id, edu_id = run(first_upload)
    headers = auth(user_id)
    client.patch(f"/profile/experiences/{exp_id}", headers=headers, json={"action": "hide"})
    client.patch(f"/profile/education/{edu_id}", headers=headers, json={"action": "confirm"})

    async def second_upload(db):
        resume = Resume(user_id=user_id, raw_text="two")
        db.add(resume)
        await db.flush()
        db.add_all([
            Experience(user_id=user_id, resume_id=resume.id, role="Engineer", company="Acme", bullets=["a"]),
            Education(user_id=user_id, resume_id=resume.id, institution="State U", degree="BSc"),
        ])
        await db.commit()
        await carry_over_reviews(db, user_id, resume.id)
        exp = (await db.execute(select(Experience).where(Experience.resume_id == resume.id))).scalar_one()
        edu = (await db.execute(select(Education).where(Education.resume_id == resume.id))).scalar_one()
        return exp.is_hidden, edu.review_state
    assert run(second_upload) == (True, "confirmed")


# ----------------------------------------------------------------- cached reports

def test_a_cached_report_goes_stale_when_the_evidence_changes(user_id):
    project_id = add_resume_project(user_id, "Audited")
    report = {
        "facts": {"project_name": "Audited", "has_repo_match": True},
        "narrative": {"headline": "h"},
    }

    async def cache_report(db):
        db.add(ProjectClaimAuditReview(user_id=user_id, project_id=project_id, report_json=report,
                                       created_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
        await db.commit()
    run(cache_report)

    assert run(lambda db: get_cached_claim_audit_report(db, user_id, project_id)) is not None  # nothing changed yet
    assert run(lambda db: evidence_cutoff(db, user_id)) is None

    run(lambda db: touch_evidence(db, user_id))  # e.g. a GitHub sync, an upload, an edit

    assert run(lambda db: get_cached_claim_audit_report(db, user_id, project_id)) is None  # out of date

    async def regenerate(db):
        row = (await db.execute(select(ProjectClaimAuditReview).where(
            ProjectClaimAuditReview.project_id == project_id))).scalar_one()
        row.created_at = datetime.now(timezone.utc)
        await db.commit()
    run(regenerate)
    assert run(lambda db: get_cached_claim_audit_report(db, user_id, project_id)) is not None  # fresh again


def test_editing_the_record_marks_cached_reports_out_of_date(user_id, client):
    project_id = add_resume_project(user_id, "Edited Later")
    assert run(lambda db: evidence_cutoff(db, user_id)) is None

    client.patch(f"/profile/projects/{project_id}", headers=auth(user_id), json={"action": "confirm"})

    assert run(lambda db: evidence_cutoff(db, user_id)) is not None
