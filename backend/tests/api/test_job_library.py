"""The job library: the primary target, deleting and comparing saved jobs,
and the career planner and interview practice reading the target.

Real endpoints on the real database. Only LLM calls and the identity refresh
are stubbed.
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.facts import Project, Resume, User
from app.models.goals import Goal
from app.models.inference import SkillEvidence
from app.models.job_intelligence import (
    CompanyIntelligenceProfileRow,
    GapAnalysisResultRow,
    JobIntelligenceProfileRow,
)
from app.models.tailored_resume import TailoredResume
from app.schemas.interview.interview_response import GroundingReport
from app.services.career_planner.context_builder import build_career_plan_context
from app.services.evidence.state import touch_evidence
from app.services.skill_gap.narrative import InterpretationError
from app.services.skill_gap.prioritization import PrioritizationError
from tests.api.test_evidence import auth, run
from tests.api.test_skill_gap_evidence import _requirement, _skill


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


@pytest.fixture
def interview_contexts(monkeypatch):
    """Stubs interview generation and records the context it was given."""
    seen = []

    async def classify(question, trace_id=None):
        return "behavioral"

    async def generate(context, blueprint_key, trace_id=None):
        seen.append(context)
        return SimpleNamespace(
            question_type="behavioral", blueprint_used=blueprint_key, answer="a", answer_short="a",
            stories_used=[], competencies=[], follow_up_questions=[], coaching=[], insufficient_context=False,
            insufficient_context_reason="", context_note="", claims_needing_verification=[],
            grounding=GroundingReport(), prompt_version="",
        )

    monkeypatch.setattr("app.api.interview.classify_blueprint", classify)
    monkeypatch.setattr("app.api.interview.generate_interview_response", generate)
    return seen


def new_user():
    async def create(db):
        user = User(name="Ivy", email=f"{uuid.uuid4().hex}@example.test", auth_provider="local",
                    target_roles=[], target_companies=[])
        db.add(user)
        await db.flush()
        resume = Resume(user_id=user.id, raw_text="r")
        db.add(resume)
        await db.flush()
        project = Project(user_id=user.id, resume_id=resume.id, name="Ledger", source="resume",
                          description="Uses Python.", stack=["python"])
        db.add(project)
        await db.flush()
        skill = await _skill(db, "python")
        db.add(SkillEvidence(user_id=user.id, skill_id=skill.id, source_type="project",
                             source_id=project.id, weight=0.9, created_at=datetime.now(timezone.utc)))
        await db.commit()
        return SimpleNamespace(id=user.id, resume_id=resume.id)
    return run(create)


def add_job(user, role, required=(), nice=(), *, company="Globex", source_hash=None, age_days=0):
    async def go(db):
        created = datetime.now(timezone.utc) - timedelta(days=age_days)
        source = source_hash or uuid.uuid4().hex
        job = JobIntelligenceProfileRow(
            user_id=user.id, source_text_hash=source, created_at=created,
            profile_json={
                "role": role, "company": company,
                "enriched_required_skills": [_requirement(s, "required") for s in required],
                "enriched_nice_to_have": [_requirement(s, "nice_to_have") for s in nice],
            },
        )
        db.add(job)
        db.add(CompanyIntelligenceProfileRow(
            user_id=user.id, source_text_hash=source, created_at=created, profile_json={"company": company},
        ))
        await db.commit()
        return str(job.id)
    return run(go)


def add_goal(user, title, job_id=None):
    async def go(db):
        goal = Goal(user_id=user.id, title=title, status_pct=0.0,
                    job_intelligence_id=uuid.UUID(job_id) if job_id else None)
        db.add(goal)
        await db.commit()
        return goal.id
    return run(go)


def listing(client, user):
    response = client.get("/job-intelligence", headers=auth(user.id))
    assert response.status_code == 200, response.text[:300]
    return response.json()


def make_primary(client, user, job_id):
    response = client.put(f"/job-intelligence/{job_id}/primary", headers=auth(user.id))
    assert response.status_code == 200, response.text[:300]


def primaries(client, user):
    return [j["id"] for j in listing(client, user) if j["is_primary"]]


# --- primary target ---------------------------------------------------------

def test_one_job_is_the_primary_target_and_it_is_listed_first(client, seeded):
    user = new_user()
    older = add_job(user, "Data Engineer", age_days=5)
    newer = add_job(user, "Backend Engineer")
    assert [j["id"] for j in listing(client, user)] == [newer, older]
    assert primaries(client, user) == []

    make_primary(client, user, older)
    assert [j["id"] for j in listing(client, user)] == [older, newer]

    make_primary(client, user, newer)
    make_primary(client, user, newer)  # repeating is harmless
    assert primaries(client, user) == [newer]


def test_the_primary_target_can_be_cleared(client, seeded):
    user = new_user()
    first, second = add_job(user, "A"), add_job(user, "B")
    make_primary(client, user, first)

    # Clearing a job that isn't primary leaves the primary one alone.
    assert client.delete(f"/job-intelligence/{second}/primary", headers=auth(user.id)).status_code == 200
    assert primaries(client, user) == [first]

    assert client.delete(f"/job-intelligence/{first}/primary", headers=auth(user.id)).status_code == 200
    assert primaries(client, user) == []


def test_each_user_has_their_own_primary_target(client, seeded):
    ivy, other = new_user(), new_user()
    hers, theirs = add_job(ivy, "A"), add_job(other, "B")
    make_primary(client, ivy, hers)
    make_primary(client, other, theirs)

    assert primaries(client, ivy) == [hers]
    assert client.put(f"/job-intelligence/{theirs}/primary", headers=auth(ivy.id)).status_code == 404
    assert primaries(client, ivy) == [hers]


# --- delete -----------------------------------------------------------------

def stored_for(user, job_id):
    async def go(db):
        async def count(model, *where):
            return len((await db.execute(select(model).where(model.user_id == user.id, *where))).scalars().all())
        target = uuid.UUID(job_id)
        return {
            "job": await count(JobIntelligenceProfileRow, JobIntelligenceProfileRow.id == target),
            "gap": await count(GapAnalysisResultRow, GapAnalysisResultRow.job_intelligence_id == target),
            "resume": await count(TailoredResume, TailoredResume.job_intelligence_id == target),
            "companies": await count(CompanyIntelligenceProfileRow),
        }
    return run(go)


def test_deleting_a_job_removes_its_results_and_keeps_the_goal(client, seeded):
    user = new_user()
    doomed = add_job(user, "Backend Engineer", ["python"])
    kept = add_job(user, "Data Engineer", ["sql"])
    for job_id in (doomed, kept):
        assert client.get(f"/jobs/by-intelligence/{job_id}", headers=auth(user.id)).status_code == 200

    async def add_resume(db):
        db.add(TailoredResume(user_id=user.id, job_intelligence_id=uuid.UUID(doomed), version=1,
                              content_json={}, created_at=datetime.now(timezone.utc)))
        await db.commit()
    run(add_resume)
    goal_id = add_goal(user, "Get the backend job", doomed)
    make_primary(client, user, doomed)

    response = client.delete(f"/job-intelligence/{doomed}", headers=auth(user.id))

    assert response.status_code == 200, response.text[:300]
    assert stored_for(user, doomed) == {"job": 0, "gap": 0, "resume": 0, "companies": 1}
    assert stored_for(user, kept) == {"job": 1, "gap": 1, "resume": 0, "companies": 1}
    assert [j["id"] for j in listing(client, user)] == [kept]
    assert primaries(client, user) == []

    async def goal(db):
        return await db.get(Goal, goal_id)
    assert run(goal).job_intelligence_id is None
    assert client.delete(f"/job-intelligence/{doomed}", headers=auth(user.id)).status_code == 404


def test_company_details_stay_while_another_copy_of_the_posting_remains(client, seeded):
    user = new_user()
    first = add_job(user, "Backend Engineer", source_hash="same-posting")
    second = add_job(user, "Backend Engineer", source_hash="same-posting")

    client.delete(f"/job-intelligence/{first}", headers=auth(user.id))
    assert stored_for(user, second)["companies"] == 2

    client.delete(f"/job-intelligence/{second}", headers=auth(user.id))
    assert stored_for(user, second)["companies"] == 0


# --- compare ----------------------------------------------------------------

def compare(client, user, *ids):
    return client.get("/job-intelligence/compare", headers=auth(user.id), params={"ids": list(ids)})


def test_comparison_lines_up_each_jobs_requirements_against_the_user(client, seeded):
    user = new_user()
    backend = add_job(user, "Backend Engineer", ["python", "kafka"], ["docker"])
    data = add_job(user, "Data Engineer", ["sql", "python"], ["kafka"])
    make_primary(client, user, data)

    response = compare(client, user, backend, data)

    assert response.status_code == 200, response.text[:300]
    body = response.json()
    assert [(j["id"], j["is_primary"]) for j in body["jobs"]] == [(backend, False), (data, True)]
    rows = {row["skill"]: row for row in body["skills"]}
    assert rows["python"]["status"] == "have"
    assert rows["kafka"]["status"] == "missing"
    assert rows["kafka"]["bands"] == {backend: "required", data: "nice_to_have"}
    assert rows["docker"]["bands"] == {backend: "nice_to_have"}
    # Shared requirements first, then required ones.
    assert [row["skill"] for row in body["skills"]] == ["kafka", "python", "sql", "docker"]


def test_comparison_scores_match_the_skill_gap_page(client, seeded):
    user = new_user()
    jobs = [add_job(user, "A", ["python", "kafka"]), add_job(user, "B", ["python"], ["sql"])]

    compared = {j["id"]: j["overall_match"] for j in compare(client, user, *jobs).json()["jobs"]}

    for job_id in jobs:
        page = client.get(f"/jobs/by-intelligence/{job_id}", headers=auth(user.id)).json()
        assert compared[job_id] == page["overall_match"]


def test_a_job_with_no_skills_gets_no_score(client, seeded):
    user = new_user()
    jobs = compare(client, user, add_job(user, "A", ["python"]), add_job(user, "Empty")).json()["jobs"]
    assert jobs[1]["overall_match"] is None


def test_comparison_needs_two_to_four_of_the_users_own_jobs(client, seeded):
    user, other = new_user(), new_user()
    mine = [add_job(user, f"Job {i}") for i in range(5)]
    theirs = add_job(other, "Private")

    assert compare(client, user, mine[0]).status_code == 400
    assert compare(client, user, mine[0], mine[0]).status_code == 400
    assert compare(client, user, *mine).status_code == 400
    assert compare(client, user, *mine[:4]).status_code == 200
    assert compare(client, user, mine[0], theirs).status_code == 404


# --- career planner ---------------------------------------------------------

def plan_target(user, goal_id):
    async def go(db):
        goal = await db.get(Goal, goal_id)
        return (await build_career_plan_context(db, user.id, goal))["target_job"]
    return run(go)


def test_a_goal_without_a_job_plans_for_the_primary_target(client, seeded):
    user = new_user()
    target = add_job(user, "Backend Engineer", ["kafka", "python", "kubernetes"], ["docker"], age_days=5)
    add_job(user, "Data Engineer", ["sql"])
    make_primary(client, user, target)

    context = plan_target(user, add_goal(user, "Level up"))

    # Never compared before, yet the planner knows where the user stands.
    assert context["role"] == "Backend Engineer"
    assert context["have_skills"] == ["python"]
    # Worst gaps first, then the order they'd be learned in.
    assert [m["skill"] for m in context["missing_skills"]] == ["kubernetes", "kafka", "docker"]
    assert all(m["estimated_weeks"] >= 1 for m in context["missing_skills"])
    assert context["overall_match_percentage"] is not None


def test_a_goals_own_job_comes_before_the_primary_target(client, seeded):
    user = new_user()
    target = add_job(user, "Backend Engineer")
    own = add_job(user, "Data Engineer", ["sql"])
    make_primary(client, user, target)

    assert plan_target(user, add_goal(user, "Data", own))["role"] == "Data Engineer"


def test_without_a_primary_target_the_last_compared_job_is_used(client, seeded):
    user = new_user()
    compared = add_job(user, "Backend Engineer", ["kafka"], age_days=5)
    add_job(user, "Data Engineer")
    goal = add_goal(user, "Level up")
    assert plan_target(user, goal) is None

    client.get(f"/jobs/by-intelligence/{compared}", headers=auth(user.id))
    assert plan_target(user, goal)["role"] == "Backend Engineer"


def test_the_planner_does_not_use_an_out_of_date_comparison(client, seeded):
    user = new_user()
    job = add_job(user, "Backend Engineer", ["python"])
    make_primary(client, user, job)
    goal = add_goal(user, "Level up")
    client.get(f"/jobs/by-intelligence/{job}", headers=auth(user.id))
    assert plan_target(user, goal)["have_skills"] == ["python"]

    async def lose_the_evidence(db):
        for row in (await db.execute(select(SkillEvidence).where(SkillEvidence.user_id == user.id))).scalars():
            await db.delete(row)
        await touch_evidence(db, user.id)
        await db.commit()
    run(lose_the_evidence)

    assert plan_target(user, goal)["have_skills"] == []


# --- interview practice -----------------------------------------------------

def ask(client, user, **payload):
    response = client.post("/interview/ask", headers=auth(user.id),
                           json={"question": "Tell me about yourself", **payload})
    assert response.status_code == 200, response.text[:400]
    return response.json()


def practised_role(contexts):
    job = contexts[-1]["target_job_intelligence"]
    return job and job["role"]


def test_interview_practice_uses_the_primary_target_over_a_goal(client, seeded, interview_contexts):
    user = new_user()
    target = add_job(user, "Backend Engineer", company="Initech")
    goal_job = add_job(user, "Data Engineer")
    add_goal(user, "Data", goal_job)
    make_primary(client, user, target)

    answer = ask(client, user)

    assert practised_role(interview_contexts) == "Backend Engineer"
    assert interview_contexts[-1]["target_role"] == "Backend Engineer"
    assert interview_contexts[-1]["target_company"] == "Initech"
    assert answer["job_intelligence_id"] == target
    assert answer["auto_attached_job_intelligence_id"] == target
    assert answer["job_context_source"] == "primary"


def test_a_job_chosen_for_the_session_wins(client, seeded, interview_contexts):
    user = new_user()
    target, chosen = add_job(user, "Backend Engineer"), add_job(user, "Data Engineer")
    make_primary(client, user, target)

    answer = ask(client, user, job_intelligence_id=chosen)

    assert practised_role(interview_contexts) == "Data Engineer"
    assert answer["job_intelligence_id"] == chosen
    assert answer["auto_attached_job_intelligence_id"] is None


def test_a_typed_target_is_not_mixed_with_another_jobs_requirements(client, seeded, interview_contexts):
    user = new_user()
    target = add_job(user, "Backend Engineer", company="Initech")
    make_primary(client, user, target)

    answer = ask(client, user, target_role="Product Manager")
    assert practised_role(interview_contexts) is None
    assert answer["job_intelligence_id"] is None

    ask(client, user, target_role="Backend Engineer", target_company="Other Corp")
    assert practised_role(interview_contexts) is None

    ask(client, user, target_role="backend engineer ", target_company="Initech")
    assert practised_role(interview_contexts) == "Backend Engineer"


def test_without_a_primary_target_the_active_goals_job_is_used(client, seeded, interview_contexts):
    user = new_user()
    job = add_job(user, "Data Engineer")
    add_goal(user, "Data", job)

    answer = ask(client, user)

    assert practised_role(interview_contexts) == "Data Engineer"
    assert answer["job_context_source"] == "goal"


def test_a_correction_keeps_the_job_the_answer_was_written_for(client, seeded, interview_contexts):
    user = new_user()
    chosen, later = add_job(user, "Data Engineer"), add_job(user, "Backend Engineer")
    first = ask(client, user, job_intelligence_id=chosen)
    make_primary(client, user, later)

    response = client.post("/interview/correct", headers=auth(user.id),
                           json={"parent_response_id": first["response_id"], "correction": "Shorter"})

    assert response.status_code == 200, response.text[:400]
    assert practised_role(interview_contexts) == "Data Engineer"
    assert response.json()["job_intelligence_id"] == chosen
