"""The study plan for a job, and the career plan built around it. Real database;
stand-in model.
"""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from openai import RateLimitError

from app.core import llm
from app.models.facts import LeetcodeSnapshot, UserSkillOverride
from app.models.goals import Goal
from app.models.inference import CareerPlan
from app.models.interview_kit import PracticeAttempt
from app.schemas.interview.kit import InterviewKitDraft, KitQuestion
from app.services.career_planner.context_builder import build_career_plan_context
from app.services.evidence.state import touch_evidence
from app.services.interview.kit_store import save_new_kit
from app.services.interview.study_plan import build_study_plan
from tests.api.test_evidence import auth, run
from tests.api.test_resume_rewriting import DOCKER, KUBERNETES, POSTGRES, REDIS, add_job
from tests.api.test_resume_selection import evidence, experience, new_user
from tests.api.test_skill_gap_evidence import _skill
from tests.llm_stub import api_error, model  # noqa: F401 (model is a fixture)

NOW = datetime.now(timezone.utc)
ALGORITHMS, SYSTEMS = ("Algorithms and problem solving", "algorithms"), ("System design", "system_design")


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "test-key")


def study(user, job_id):
    async def go(db):
        return await build_study_plan(db, user.id, uuid.UUID(job_id))
    return run(go)


def shows(user, canonical, weight):
    """A role that is evidence of the skill, this strongly."""
    item = experience(user, f"Role {canonical}", [canonical], [f"Used {canonical}."])
    evidence(user, canonical, "experience", item, weight=weight)


def solved(user, **tags):
    async def go(db):
        db.add_all([LeetcodeSnapshot(user_id=user.id, tag=tag.replace("_", "-"), solved_count=count, pulled_at=NOW)
                    for tag, count in tags.items()])
        await db.commit()
    run(go)


def hide_skill(user, canonical):
    async def go(db):
        skill = await _skill(db, canonical)
        db.add(UserSkillOverride(user_id=user.id, skill_id=skill.id, is_hidden=True, updated_at=NOW))
        await db.commit()
    run(go)


def gap(plan, skill):
    return next(g for g in plan.gaps if g.skill == skill)


# --- the gaps ---------------------------------------------------------------

def test_a_skill_the_record_shows_well_is_not_a_gap(seeded):
    user = new_user()
    shows(user, "postgres", 0.9)
    job = add_job(user, [POSTGRES, KUBERNETES])

    plan = study(user, job)

    assert [g.skill for g in plan.gaps] == ["kubernetes"]
    assert (plan.role, plan.company, str(plan.job_intelligence_id)) == ("Backend Engineer", "Globex", job)


def test_gaps_come_most_pressing_first(seeded):
    user = new_user()
    shows(user, "postgres", 0.4)  # shown thinly
    job = add_job(user, [POSTGRES, KUBERNETES, ("Python", "python")], nice=[DOCKER])

    plan = study(user, job)

    # By severity, then in the order skills are usually learnt, not by name.
    assert [(g.skill, g.status, g.severity, g.requirement) for g in plan.gaps] == [
        ("python", "missing", "critical", "required"),
        ("kubernetes", "missing", "critical", "required"),
        ("postgres", "partial", "moderate", "required"),
        ("docker", "missing", "minor", "nice_to_have"),
    ]


def test_each_gap_says_why_and_what_to_do(seeded):
    user = new_user()
    shows(user, "postgres", 0.4)
    shows(user, "docker", 0.1)
    shows(user, "redis", 0.9)
    hide_skill(user, "redis")
    job = add_job(user, [POSTGRES, DOCKER, REDIS, KUBERNETES])

    plan = study(user, job)

    reasons = {g.skill: g.why for g in plan.gaps}
    assert reasons == {
        "postgres": "Your record shows it only thinly.",
        "docker": "Your record shows too little of it to count.",
        "redis": "You hid this skill from your record.",
        "kubernetes": "Nothing in your record shows it.",
    }
    assert "restore it" in gap(plan, "redis").action
    assert "Build or write up work" in gap(plan, "docker").action
    assert "Learn it" in gap(plan, "kubernetes").action


def test_a_gap_is_named_as_the_job_writes_it(seeded):
    user = new_user()

    assert study(user, add_job(user, [ALGORITHMS])).gaps[0].name == "Algorithms and problem solving"


def test_a_gap_leetcode_covers_links_to_topics_with_what_is_solved(seeded):
    user = new_user()
    solved(user, sliding_window=2, greedy=1)
    job = add_job(user, [ALGORITHMS, SYSTEMS])

    plan = study(user, job)

    practice = gap(plan, "algorithms")
    assert len(practice.leetcode) == 5
    assert all(t.solved is not None for t in practice.leetcode)
    assert "least practised first" in practice.action
    assert gap(plan, "system_design").leetcode == []
    assert not any("Sync LeetCode" in note for note in plan.notes)


def test_without_a_leetcode_sync_nothing_is_claimed_to_be_solved(seeded):
    user = new_user()

    plan = study(user, add_job(user, [ALGORITHMS]))

    assert {t.solved for t in plan.gaps[0].leetcode} == {None}
    assert any("Sync LeetCode" in note for note in plan.notes)


def test_enough_practice_closes_the_gap(seeded):
    user = new_user()
    shows(user, "algorithms", 0.75)
    job = add_job(user, [ALGORITHMS])

    assert study(user, job).gaps == []


def test_a_job_with_no_skills_has_no_gaps(seeded):
    user = new_user()

    assert study(user, add_job(user, [])).gaps == []


# --- with an interview kit ----------------------------------------------------

def question(text, skills=(), thin=False, category="technical_depth"):
    return KitQuestion(category=category, topic=text, text=text, skills=list(skills), thin_evidence=thin)


def save_kit(user, job_id, *questions, scores=None, mapped_at=None):
    """Saves a kit, with a practice attempt for each score given (by position)."""
    async def go(db):
        draft = InterviewKitDraft(seniority="mid", questions=list(questions), evidence_mapped_at=mapped_at or NOW
                                  + timedelta(minutes=5))
        saved = await save_new_kit(db, user.id, uuid.UUID(job_id), draft)
        for position, score in (scores or {}).items():
            db.add(PracticeAttempt(
                user_id=user.id, question_id=saved.questions[position].id, answer="a", score=score,
                feedback_json={"headings": []}, created_at=datetime.now(timezone.utc),
            ))
        await db.commit()
    run(go)


def texts(questions) -> list[str]:
    return [q.text for q in questions]


def test_the_kits_questions_are_listed_under_the_gaps_they_ask_about(seeded):
    user = new_user()
    shows(user, "postgres", 0.9)
    job = add_job(user, [POSTGRES, KUBERNETES])
    save_kit(
        user, job,
        question("About pods", ["kubernetes"], thin=True),
        question("About indexes", ["postgres"]),
        question("About both", ["postgres", "kubernetes"]),
        question("About a disagreement", thin=True, category="behavioral"),
        question("About the schema", ["postgres"], thin=True),
    )

    plan = study(user, job)

    assert texts(gap(plan, "kubernetes").questions) == ["About pods", "About both"]
    # Thin questions that no gap accounts for need an example of their own.
    assert texts(plan.unanswered) == ["About a disagreement", "About the schema"]
    assert (plan.kit_version, plan.weak, plan.notes) == (1, [], [])


def test_poorly_answered_questions_are_listed_for_another_go(seeded):
    user = new_user()
    job = add_job(user, [])
    save_kit(
        user, job, question("Poor"), question("Half", category="behavioral"), question("Unscored"),
        question("Never"), scores={0: 0.2, 1: 0.5, 2: None},
    )

    plan = study(user, job)

    assert [(q.text, q.latest_score) for q in plan.weak] == [("Poor", 0.2)]
    assert plan.weakest_category == "technical_depth"


def test_the_newest_kit_is_the_one_used(seeded):
    user = new_user()
    job = add_job(user, [KUBERNETES])
    save_kit(user, job, question("Old", ["kubernetes"]))
    save_kit(user, job, question("New", ["kubernetes"]))

    plan = study(user, job)

    assert (plan.kit_version, texts(plan.gaps[0].questions)) == (2, ["New"])


def test_a_kit_matched_before_the_record_changed_is_said_to_be_out_of_date(seeded):
    user = new_user()
    job = add_job(user, [KUBERNETES])
    save_kit(user, job, question("Q"), mapped_at=NOW - timedelta(days=1))

    async def change(db):
        await touch_evidence(db, user.id)
    run(change)

    assert any("changed since" in note for note in study(user, job).notes)


def test_without_a_kit_the_gaps_still_come_with_a_note(seeded):
    user = new_user()

    plan = study(user, add_job(user, [KUBERNETES]))

    assert (plan.kit_version, plan.unanswered, plan.weakest_category) == (None, [], None)
    assert plan.gaps[0].questions == []
    assert any("Generate an interview kit" in note for note in plan.notes)


def test_no_model_is_called_and_nothing_of_another_users_is_shown(client, model):
    owner, other = new_user(), new_user()
    job = add_job(owner, [KUBERNETES])
    save_kit(owner, job, question("Secret question", ["kubernetes"]))

    assert study(other, job) is None
    assert client.get(f"/interview/study-plan/{job}", headers=auth(other.id)).status_code == 404
    mine = client.get(f"/interview/study-plan/{job}", headers=auth(owner.id))

    assert mine.status_code == 200, mine.text[:300]
    assert mine.json()["gaps"][0]["questions"][0]["text"] == "Secret question"
    assert model.requests == []


# --- the career planner -----------------------------------------------------

def add_goal(user, job_id, title="Level up", days=2):
    async def go(db):
        goal = Goal(user_id=user.id, title=title, status_pct=0.0, deadline=date.today() + timedelta(days=days),
                    job_intelligence_id=uuid.UUID(job_id) if job_id else None)
        db.add(goal)
        await db.commit()
        return goal.id
    return run(go)


def context_for(user, goal_id):
    async def go(db):
        return await build_career_plan_context(db, user.id, await db.get(Goal, goal_id))
    return run(go)


def a_goal(*skills, days=2, **kit):
    user = new_user()
    job = add_job(user, list(skills))
    return user, job, add_goal(user, job, days=days)


def days(*items):
    return {"daily_plan": [{"day": n, "theme": theme, "tasks": tasks} for n, (theme, tasks) in
                           enumerate(items, start=1)]}


def plan_for(client, user, goal_id):
    response = client.post(f"/goals/{goal_id}/plan", headers=auth(user.id))
    assert response.status_code == 200, response.text[:300]
    return response.json()


def test_the_planner_is_given_the_target_jobs_gaps(seeded):
    user, job, goal = a_goal(KUBERNETES, ALGORITHMS)

    found = context_for(user, goal)["study_plan"]

    assert sorted(g["skill"] for g in found["gaps"]) == ["algorithms", "kubernetes"]
    assert found["job_intelligence_id"] == job


def test_a_goal_with_no_job_has_no_study_plan(seeded):
    user = new_user()

    assert context_for(user, add_goal(user, None))["study_plan"] is None


def test_a_long_study_plan_is_cut_to_what_days_can_use(seeded):
    user = new_user()
    job = add_job(user, [(f"Tool {n}", f"tool_{n}") for n in range(20)])
    save_kit(user, job, *[question(f"About tool 0, {n}", ["tool_0"]) for n in range(4)],
             *[question(f"Story {n}", thin=True) for n in range(8)])

    found = context_for(user, add_goal(user, job))["study_plan"]

    assert len(found["gaps"]) == 12
    assert max(len(g["questions"]) for g in found["gaps"]) == 2
    assert len(found["unanswered"]) == 5


def test_the_model_is_sent_the_gaps_without_ids_or_addresses(client, model):
    user, job, goal = a_goal(ALGORITHMS)
    save_kit(user, job, question("Explain a heap", ["algorithms"]))
    model.will(days(("A", ["x"]), ("B", ["y"])))

    plan_for(client, user, goal)

    sent = json.loads(model.requests[0]["messages"][1]["content"])["study_plan"]
    assert sent["gaps"][0]["name"] == "Algorithms and problem solving"
    assert sent["gaps"][0]["interview_questions"] == ["Explain a heap"]
    assert set(sent["gaps"][0]["leetcode_topics"][0]) == {"topic", "solved"}
    assert "leetcode.com" not in json.dumps(sent) and job not in json.dumps(sent)


def test_a_plan_links_its_leetcode_days_and_ignores_any_link_the_model_sends(client, model):
    user, _job, goal = a_goal(ALGORITHMS)
    reply = days(("Windows", ["Solve a LeetCode Sliding Window problem."]), ("Reading", ["Read about queues."]))
    reply["daily_plan"][0]["links"] = [{"topic": "Invented", "url": "https://evil.invalid/"}]
    reply["daily_plan"][1]["links"] = "https://evil.invalid/"
    model.will(reply)

    plan = plan_for(client, user, goal)

    assert [[link["url"] for link in day["links"]] for day in plan["daily_plan"]] == [
        ["https://leetcode.com/tag/sliding-window/"], []]
    assert plan["study_plan"]["gaps"][0]["skill"] == "algorithms"
    assert plan["degraded"] is False

    async def saved(db):
        return await db.get(CareerPlan, uuid.UUID(plan["plan_id"]))
    stored = run(saved).plan_json
    assert stored["study_plan"] == plan["study_plan"]
    assert stored["daily_plan"] == plan["daily_plan"]


def test_without_the_model_the_days_work_through_the_gaps_first(client, model):
    user, _job, goal = a_goal(ALGORITHMS, KUBERNETES, days=4)
    model.will(*[api_error(RateLimitError, 429)] * 4)

    plan = plan_for(client, user, goal)

    themes = [day["theme"] for day in plan["daily_plan"]]
    gaps = [f"Strengthen {g['name']}" for g in plan["study_plan"]["gaps"]]
    assert themes[:2] == gaps
    assert len(set(themes)) == 4  # then the goal's curriculum, without repeats
    practice = next(d for d in plan["daily_plan"] if "Algorithms" in d["theme"])
    assert "on LeetCode in " in practice["tasks"][-1]
    assert len(practice["links"]) == 1
    assert "gap for the target job" in practice["rationale"]
    other = next(d for d in plan["daily_plan"] if "Kubernetes" in d["theme"])
    assert (len(other["tasks"]), other["links"]) == (1, [])
    assert plan["degraded"] is True


def test_a_plan_without_a_job_is_as_before(client, model):
    user = new_user()
    goal = add_goal(user, None, "Crack coding interviews", days=1)
    model.will(days(("Arrays", ["Solve a LeetCode Stack problem."])))

    plan = plan_for(client, user, goal)

    assert (plan["study_plan"], plan["daily_plan"][0]["links"]) == (None, [])
