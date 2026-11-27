"""Every met requirement links to the evidence behind it, and every gap has
a severity.

Runs the real skill-gap endpoint on the real database. Only the LLM calls
(narrative, gap ordering) and the identity refresh are stubbed.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.facts import Experience, LeetcodeSnapshot, Project, Resume, User
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import SkillEvidence
from app.models.job_intelligence import GapAnalysisResultRow, JobIntelligenceProfileRow
from app.models.structure import Skill, SkillAlias
from app.schemas.resume.extraction import ExtractedExperience, ExtractionResult
from app.services.evidence.confidence import get_all_skill_confidences
from app.services.projects.reconcile import reconcile_projects
from app.services.resume.ingestion import ingest_resume
from app.services.skill_gap.narrative import InterpretationError
from app.services.skill_gap.prioritization import PrioritizationError
from tests.api.test_evidence import auth, run


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    async def no_narrative(context):
        raise InterpretationError("stubbed")

    async def no_ordering(context):
        raise PrioritizationError("stubbed")

    async def nothing(*args, **kwargs):
        return None

    monkeypatch.setattr("app.api.jobs.generate_narrative_analysis", no_narrative)
    monkeypatch.setattr("app.services.skill_gap.comparison.prioritize_missing_skills", no_ordering)
    monkeypatch.setattr("app.api.jobs.trigger_identity_refresh", nothing)


async def _skill(db, canonical):
    await db.execute(pg_insert(Skill).values(
        id=uuid.uuid4(), name=canonical, canonical_name=canonical,
    ).on_conflict_do_nothing(index_elements=["canonical_name"]))
    return (await db.execute(select(Skill).where(Skill.canonical_name == canonical))).scalar_one()


def _requirement(canonical, requirement_type):
    return {
        "raw": canonical, "canonical": canonical, "category": "Other",
        "curriculum_phase": "core", "requirement_type": requirement_type,
    }


@pytest.fixture
def scenario(seeded):
    """A user with a resume project, an experience, a synced repo and LeetCode
    history, plus a job asking for things they have, half-have and lack.
    """
    async def build(db):
        user = User(name="Gus", email=f"{uuid.uuid4().hex}@example.test", auth_provider="local",
                    target_roles=[], target_companies=[])
        db.add(user)
        await db.flush()
        resume = Resume(user_id=user.id, raw_text="r")
        db.add(resume)
        await db.flush()

        experience = Experience(
            user_id=user.id, resume_id=resume.id, role="Engineer", company="Acme", source="resume",
            stack=["fastapi"],
            bullets=["Led a team of three.", "Deployed services with Docker to production."],
        )
        project = Project(
            user_id=user.id, resume_id=resume.id, name="Ledger", source="resume",
            description="A bookkeeping tool. Uses PostgreSQL for storage.", stack=["python"],
        )
        repo = GithubProjectAnalysis(
            user_id=user.id, repo_name="infra-kit", description="infra", html_url="https://github.com/g/infra-kit",
            category="Backend", technologies=["Docker", "Python"], capabilities=[],
            computed_at=datetime.now(timezone.utc),
        )
        db.add_all([experience, project, repo])
        await db.flush()

        db.add(LeetcodeSnapshot(user_id=user.id, tag="Dynamic Programming", solved_count=4,
                                pulled_at=datetime.now(timezone.utc) - timedelta(days=30)))
        db.add(LeetcodeSnapshot(user_id=user.id, tag="Dynamic Programming", solved_count=12,
                                pulled_at=datetime.now(timezone.utc)))
        await db.execute(pg_insert(SkillAlias).values(
            id=uuid.uuid4(), raw_string="dynamic programming", canonical_name="dynamic_programming",
            is_valid_skill=True, created_at=datetime.now(timezone.utc),
        ).on_conflict_do_nothing(index_elements=["raw_string"]))

        rows = [
            ("python", "project", project.id, 0.35),
            ("python", "github_repo", repo.id, 0.30),
            ("docker", "experience", experience.id, 0.25),
            ("docker", "github_repo", repo.id, 0.39),
            ("postgres", "project", project.id, 0.35),
            ("fastapi", "experience", experience.id, 0.14),
            ("dynamic_programming", "leetcode_tag", None, 0.35),
        ]
        for canonical, source_type, source_id, weight in rows:
            skill = await _skill(db, canonical)
            db.add(SkillEvidence(user_id=user.id, skill_id=skill.id, source_type=source_type,
                                 source_id=source_id, weight=weight, created_at=datetime.now(timezone.utc)))

        job = JobIntelligenceProfileRow(
            user_id=user.id, source_text_hash=uuid.uuid4().hex, created_at=datetime.now(timezone.utc),
            profile_json={
                "role": "Backend Engineer", "company": "Globex",
                "enriched_required_skills": [_requirement(s, "required")
                                             for s in ("python", "docker", "postgres", "kubernetes")],
                "enriched_implicit_skills": [_requirement(s, "implicit")
                                             for s in ("fastapi", "dynamic_programming")],
                "enriched_nice_to_have": [_requirement("graphql", "nice_to_have")],
            },
        )
        db.add(job)
        await db.commit()
        await reconcile_projects(db, user.id)  # gives infra-kit its project
        return {"user_id": user.id, "job_id": job.id, "project_id": project.id,
                "experience_id": experience.id, "resume_id": resume.id}
    return run(build)


def gap(client, scenario, **params):
    response = client.get(f"/jobs/by-intelligence/{scenario['job_id']}", headers=auth(scenario["user_id"]),
                          params=params)
    assert response.status_code == 200, response.text[:400]
    return response.json()


def by_skill(report):
    return {
        entry["skill"]: (status, entry)
        for status in ("have", "partial", "missing")
        for entry in report[status]
    }


def items(entry):
    return {(i["kind"], i["title"]): i for i in entry["supporting"]}


def test_each_requirement_lands_in_the_right_bucket(client, scenario):
    result = by_skill(gap(client, scenario)["report"])

    assert {skill: status for skill, (status, _) in result.items()} == {
        "python": "have", "docker": "have",
        "postgres": "partial", "dynamic_programming": "partial",
        "kubernetes": "missing", "fastapi": "missing", "graphql": "missing",
    }


def test_every_met_requirement_links_to_evidence(client, scenario):
    report = gap(client, scenario)["report"]

    met = report["have"] + report["partial"]
    assert met and all(entry["supporting"] for entry in met)
    assert all(item["title"] for entry in met for item in entry["supporting"])


def test_the_supporting_items_name_the_bullet_sentence_repo_and_topic(client, scenario):
    result = by_skill(gap(client, scenario)["report"])

    docker = items(result["docker"][1])
    bullet = docker[("experience", "Engineer at Acme")]
    assert bullet["detail"] == "Deployed services with Docker to production."  # the bullet, not just the role
    assert bullet["item_id"] == str(scenario["experience_id"]) and bullet["source"] == "resume"
    repo = docker[("github_repo", "infra-kit")]
    assert "Docker" in repo["detail"] and repo["url"] == "https://github.com/g/infra-kit"
    assert repo["item_id"] is not None  # links to the project the repo became

    postgres = items(result["postgres"][1])[("project", "Ledger")]
    assert postgres["detail"] == "Uses PostgreSQL for storage."
    assert postgres["item_id"] == str(scenario["project_id"])

    python = items(result["python"][1])[("project", "Ledger")]
    assert python["detail"] == "Listed in the project's technologies (python)"

    topic = items(result["dynamic_programming"][1])[("leetcode_topic", "Dynamic Programming")]
    assert topic["detail"] == "12 problems solved"  # the newest count, not the older 4

    assert [i["title"] for i in result["docker"][1]["supporting"]] == ["infra-kit", "Engineer at Acme"]


def test_every_gap_has_a_severity_and_weak_evidence_is_shown(client, scenario):
    result = by_skill(gap(client, scenario)["report"])

    severities = {skill: entry["severity"] for skill, (status, entry) in result.items() if status != "have"}
    assert severities == {
        "kubernetes": "critical",           # required, nothing
        "postgres": "moderate",             # required, partial
        "fastapi": "moderate",              # implicit, not enough
        "dynamic_programming": "minor",     # implicit, partial
        "graphql": "minor",                 # nice to have, nothing
    }
    assert result["kubernetes"][1]["supporting"] == []
    assert [i["title"] for i in result["fastapi"][1]["supporting"]] == ["Engineer at Acme"]


def test_an_unchanged_record_reuses_the_stored_comparison(client, scenario):
    first = gap(client, scenario)
    second = gap(client, scenario)

    assert second["generated_at"] == first["generated_at"]


def test_hiding_a_project_removes_its_evidence_and_rebuilds_the_comparison(client, scenario):
    first = gap(client, scenario)
    headers = auth(scenario["user_id"])
    hidden = client.patch(f"/profile/projects/{scenario['project_id']}", headers=headers, json={"action": "hide"})
    assert hidden.status_code == 200

    second = gap(client, scenario)

    assert second["generated_at"] != first["generated_at"]
    result = by_skill(second["report"])
    assert result["postgres"][0] == "missing"  # only that project showed it
    every_title = [i["title"] for status in ("have", "partial", "missing")
                   for entry in second["report"][status] for i in entry["supporting"]]
    assert "Ledger" not in every_title


def test_a_hidden_skill_is_reported_as_a_gap_the_user_chose(client, scenario):
    gap(client, scenario)
    client.put("/profile/skills/docker/visibility", headers=auth(scenario["user_id"]), json={"hidden": True})

    status, docker = by_skill(gap(client, scenario)["report"])["docker"]

    assert status == "missing" and docker["severity"] == "critical"
    assert docker["reason"] == "You hid this skill from your evidence record"
    assert docker["supporting"] == []


def test_a_stored_comparison_without_evidence_links_is_rebuilt(client, scenario):
    gap(client, scenario)

    async def age(db):
        row = (await db.execute(select(GapAnalysisResultRow).where(
            GapAnalysisResultRow.job_intelligence_id == scenario["job_id"]))).scalar_one()
        report = dict(row.report_json)
        report.pop("evidence_version")
        report["have"] = [{**entry, "supporting": []} for entry in report["have"]]
        row.report_json = report
        await db.commit()
    run(age)

    rebuilt = gap(client, scenario)["report"]

    assert all(entry["supporting"] for entry in rebuilt["have"])


def test_a_newer_upload_replaces_the_old_evidence_instead_of_adding_to_it(client, scenario):
    before = run(lambda db: get_all_skill_confidences(db, scenario["user_id"]))["postgres"]

    async def reupload(db):
        resume = Resume(user_id=scenario["user_id"], raw_text="again")
        db.add(resume)
        await db.flush()
        project = Project(user_id=scenario["user_id"], resume_id=resume.id, name="Ledger", source="resume",
                          description="Rewritten. Still runs on PostgreSQL.", stack=["python"],
                          created_at=datetime.now(timezone.utc) + timedelta(seconds=5))
        db.add(project)
        await db.flush()
        skill = await _skill(db, "postgres")
        db.add(SkillEvidence(user_id=scenario["user_id"], skill_id=skill.id, source_type="project",
                             source_id=project.id, weight=0.35, created_at=datetime.now(timezone.utc)))
        await db.commit()
    run(reupload)

    after = run(lambda db: get_all_skill_confidences(db, scenario["user_id"]))["postgres"]
    assert after == pytest.approx(before)  # not doubled
    status, postgres = by_skill(gap(client, scenario, regenerate=True)["report"])["postgres"]
    assert [i["detail"] for i in postgres["supporting"]] == ["Still runs on PostgreSQL."]


def test_resume_ingestion_records_each_source_once_with_its_own_weight(seeded, monkeypatch):
    """A role with several matching bullets used to push later roles' weights
    onto the wrong rows and drop a source altogether.
    """
    async def fake_extract(raw_text):
        return ExtractionResult(experiences=[
            ExtractedExperience(role="First", company="A", stack=[],
                                bullets=["Wrote Python jobs.", "Tuned Python code.", "Taught Python."]),
            ExtractedExperience(role="Second", company="B", stack=[], bullets=["Shipped Python services."]),
            ExtractedExperience(role="Third", company="C", stack=["Python"], bullets=["Managed budgets."]),
        ])
    monkeypatch.setattr("app.services.resume.ingestion.extract_resume_data", fake_extract)

    async def go(db):
        user = User(name="Hal", email=f"{uuid.uuid4().hex}@example.test", auth_provider="local",
                    target_roles=[], target_companies=[])
        db.add(user)
        await db.commit()
        await ingest_resume("Python everywhere", db, user)
        rows = (await db.execute(
            select(Experience.role, SkillEvidence.weight)
            .join(SkillEvidence, SkillEvidence.source_id == Experience.id)
            .join(Skill, Skill.id == SkillEvidence.skill_id)
            .where(SkillEvidence.user_id == user.id, Skill.canonical_name == "python")
        )).all()
        return sorted((role, round(weight, 4)) for role, weight in rows)

    assert run(go) == [("First", 0.25), ("Second", 0.25), ("Third", 0.1375)]
