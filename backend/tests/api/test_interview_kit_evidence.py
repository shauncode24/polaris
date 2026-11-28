"""Which of the user's work is matched to each interview question. Real database;
stand-in model, and the competency keywords where no model is queued.
"""
import uuid
from datetime import datetime, timezone

import pytest
from openai import RateLimitError

from app.core import llm
from app.models.facts import Experience, LeetcodeSnapshot, Project, UserSkillOverride
from app.models.inference import ProjectClaimAuditReview
from app.schemas.interview.kit import KitQuestion, QuestionEvidence
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.services.evidence.review import apply_review
from app.services.evidence.state import touch_evidence
from app.services.interview.kit_evidence import evidence_is_stale, map_evidence, remap_kit
from app.services.interview.kit_generation import generate_interview_kit
from app.services.interview.kit_store import get_kit, save_new_kit
from tests.api.test_evidence import run
from tests.api.test_resume_rewriting import POSTGRES, add_job
from tests.api.test_resume_selection import evidence, experience, new_user, project, repo, upload
from tests.api.test_skill_gap_evidence import _skill
from tests.llm_stub import api_error, model  # noqa: F401 (model is a fixture)

NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "test-key")


def skill_question(*skills, category="technical_depth", **fields):
    return KitQuestion(**{"category": category, "topic": "Topic", "text": "A question about it?",
                          "skills": list(skills), "competencies": ["technical_depth"], **fields})


def behavioral(*competencies):
    return KitQuestion(category="behavioral", topic="A story", text="Tell me about a time?",
                       competencies=list(competencies))


def topic_question(topic, category="system_design"):
    return KitQuestion(category=category, topic=topic, text="How would you design it?",
                       competencies=["technical_depth"])


def mapping_for(user, *questions, job=None):
    async def go(db):
        return await map_evidence(db, user.id, job or JobIntelligenceProfile(), list(questions))
    return run(go)


def chosen(user, question, **kwargs) -> QuestionEvidence | None:
    refs = mapping_for(user, question, **kwargs).refs[0]
    assert len(refs) <= 1
    return refs[0] if refs else None


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


def row(model_, row_id):
    async def go(db):
        return await db.get(model_, row_id)
    return run(go)


# --- skills -----------------------------------------------------------------

def test_a_skill_question_gets_the_item_that_shows_the_skill_and_where(seeded):
    user = new_user()
    project(user, "Unrelated", ["Redis"], "Cached results.")
    wanted = experience(user, "Engineer", bullets=["Wrote handover notes.", "Tuned Postgres queries."])

    found = chosen(user, skill_question("postgres"))

    assert found == QuestionEvidence(kind="experience", id=wanted, skills=["postgres"], bullet=1)


def test_a_question_nothing_shows_is_left_empty(seeded):
    user = new_user()
    project(user, "Cache", ["Redis"], "Cached results in Redis.")

    assert chosen(user, skill_question("kubernetes")) is None


def test_a_user_with_no_work_at_all_has_every_question_empty(seeded, model):
    user = new_user()

    mapping = mapping_for(user, skill_question("postgres"), behavioral("ownership"), topic_question("Caching"))

    assert mapping.refs == [[], [], []]
    assert mapping.notice is None
    assert model.requests == []


def test_an_item_that_describes_the_skill_comes_before_one_that_only_lists_it(seeded):
    user = new_user()
    described = project(user, "Older", [], "Tuned Postgres queries.", days_ago=30)
    project(user, "Newer", ["Postgres"], "A small tool.")

    assert chosen(user, skill_question("postgres")).id == described


def test_a_skill_only_listed_still_counts_with_no_line_to_point_at(seeded):
    user = new_user()
    listed = project(user, "Tool", ["Postgres"], "A small tool.")

    found = chosen(user, skill_question("postgres"))

    assert (found.id, found.bullet) == (listed, None)


def test_the_item_showing_more_of_the_questions_skills_ranks_higher(seeded):
    user = new_user()
    both = project(user, "Both", ["Postgres", "Redis"], "Used Postgres and Redis.", days_ago=30)
    project(user, "One", ["Postgres"], "Used Postgres.")

    found = chosen(user, skill_question("postgres", "redis", category="role_specific"))

    assert (found.id, found.skills) == (both, ["postgres", "redis"])


def test_the_item_showing_the_competency_ranks_higher(seeded):
    user = new_user()
    deep = project(user, "Deep", ["Postgres"], "Optimized Postgres queries.", days_ago=30)
    project(user, "Shallow", ["Postgres"], "Used Postgres.")

    assert chosen(user, skill_question("postgres")).id == deep


def test_between_equal_items_the_most_recent_wins(seeded):
    user = new_user()
    project(user, "Older", ["Postgres"], "Used Postgres.", days_ago=30)
    newer = project(user, "Newer", ["Postgres"], "Used Postgres.")

    assert chosen(user, skill_question("postgres")).id == newer


def test_a_project_with_unsupported_claims_ranks_lower(seeded):
    user = new_user()
    sound = project(user, "Sound", ["Postgres"], "Used Postgres.", days_ago=30)
    risky = project(user, "Risky", ["Postgres"], "Used Postgres.")

    async def audit(db):
        db.add(ProjectClaimAuditReview(user_id=user.id, project_id=risky,
                                       report_json={"narrative": {"risk_level": "high"}, "facts": {}}))
        await db.commit()
    run(audit)

    assert chosen(user, skill_question("postgres")).id == sound


def test_a_repositorys_technologies_count_for_its_project(seeded):
    user = new_user()
    repo(user, "ledger", ["Kubernetes"])
    linked = project(user, "Ledger", [], "Keeps accounts.", github_repo_name="ledger")

    found = chosen(user, skill_question("kubernetes"))

    assert (found.kind, found.id, found.bullet) == ("project", linked, None)


def test_the_jobs_own_wording_for_a_skill_finds_it(seeded):
    user = new_user()
    wanted = experience(user, "Engineer", bullets=["Ran zorbing sessions for the team."])
    job = JobIntelligenceProfile.model_validate({"enriched_required_skills": [{
        "raw": "Zorbing sessions", "canonical": "zorbing_x", "category": "Other",
        "curriculum_phase": "core", "requirement_type": "required"}]})

    assert chosen(user, skill_question("zorbing_x"), job=job).id == wanted


def test_a_skill_that_is_also_a_word_needs_more_than_the_word(seeded):
    user = new_user()
    item = experience(user, "Engineer", bullets=["Helped the product go to market.", "Wrote services in Go."])

    assert chosen(user, skill_question("go")) is None

    evidence(user, "go", "experience", item)  # the record ties the skill to this role
    assert chosen(user, skill_question("go")).id == item


def test_a_hidden_skill_is_not_matched(seeded):
    user = new_user()
    project(user, "Tool", ["Postgres"], "Used Postgres.")
    solved(user, dynamic_programming=40)
    hide_skill(user, "postgres")
    hide_skill(user, "dynamic_programming")

    mapping = mapping_for(user, skill_question("postgres"), skill_question("dynamic_programming"))

    assert mapping.refs == [[], []]


def test_hidden_and_replaced_items_are_not_offered(seeded):
    user = new_user()
    old, new = upload(user, days_ago=30), upload(user)
    experience(user, "Engineer", bullets=["Tuned Postgres."], resume_id=old, days_ago=30)
    experience(user, "Engineer", bullets=["Wrote notes."], resume_id=new)
    project(user, "Hidden", ["Postgres"], "Used Postgres.", is_hidden=True)

    assert chosen(user, skill_question("postgres")) is None


def test_another_users_work_is_never_offered(seeded):
    owner, other = new_user(), new_user()
    project(owner, "Theirs", ["Postgres"], "Used Postgres.")
    solved(owner, dynamic_programming=40)

    mapping = mapping_for(other, skill_question("postgres"), skill_question("dynamic_programming"))

    assert mapping.refs == [[], []]


def test_a_role_imported_from_linkedin_can_be_offered(seeded):
    user = new_user()
    role = experience(user, "Engineer", bullets=["Tuned Postgres."], source="linkedin")

    assert chosen(user, skill_question("postgres")).id == role


# --- behavioral -------------------------------------------------------------

def test_a_behavioral_question_gets_work_showing_the_competency(seeded):
    user = new_user()
    project(user, "Solo", [], "Mentored two students.")
    led = experience(user, "Captain", bullets=["Wrote the notes.", "Led the migration."])

    found = chosen(user, behavioral("leadership"))

    assert found == QuestionEvidence(kind="experience", id=led, competencies=["leadership"], bullet=1)


@pytest.mark.parametrize("bullet,competency", [
    ("Compiled and handled the weekly reports.", "leadership"),
    ("Trained an image model.", "mentorship"),
    ("Retried failed requests.", "failure_recovery"),
    ("Resolved merge conflicts automatically.", "conflict_resolution"),
])
def test_a_word_that_only_looks_like_a_competency_is_not_evidence_of_it(seeded, bullet, competency):
    user = new_user()
    experience(user, "Engineer", bullets=[bullet])

    assert chosen(user, behavioral(competency)) is None


def test_work_the_keywords_miss_is_tagged_by_the_model_once(seeded, model):
    user = new_user()
    role = experience(user, "Engineer", bullets=[f"Saw the release through, {uuid.uuid4().hex}."])
    model.will({"results": [{"key": str(role), "tags": ["ownership"]}]})

    first = mapping_for(user, behavioral("ownership"))
    second = mapping_for(user, behavioral("ownership"))

    assert first.refs == second.refs == [[QuestionEvidence(kind="experience", id=role, competencies=["ownership"])]]
    assert first.notice is None
    assert row(Experience, role).competency_tags == ["ownership"]
    assert len(model.requests) == 1


def test_when_tagging_fails_the_user_is_told_and_it_is_tried_again(seeded, model):
    user = new_user()
    item = project(user, "Release", [], f"Saw the release through, {uuid.uuid4().hex}.")
    model.will(api_error(RateLimitError, 429), {"results": [{"key": str(item), "tags": ["ownership"]}]})

    failed = mapping_for(user, behavioral("ownership"))

    assert failed.refs == [[]]
    assert "couldn't be checked" in failed.notice
    assert row(Project, item).competency_tags is None  # not remembered as showing nothing

    again = mapping_for(user, behavioral("ownership"))
    assert (again.refs[0][0].id, again.notice) == (item, None)


def test_failed_tagging_is_not_mentioned_when_no_question_went_without(seeded, model):
    user = new_user()
    experience(user, "Captain", bullets=["Led the migration."])
    project(user, "Quiet", [], f"A thing, {uuid.uuid4().hex}.")
    model.will(api_error(RateLimitError, 429))

    assert mapping_for(user, behavioral("leadership"), skill_question("postgres")).notice is None


def test_practice_is_never_offered_for_a_behavioral_question(seeded):
    user = new_user()
    solved(user, array=80, dynamic_programming=60, graph=40)

    assert chosen(user, behavioral("problem_solving")) is None
    assert chosen(user, skill_question("dynamic_programming", category="behavioral")) is None


def review_edit(user, kind, item_id, fields):
    async def go(db):
        await apply_review(db, user.id, kind, item_id, "edit", fields)
    run(go)


def test_edited_work_is_judged_on_its_new_wording(seeded):
    user = new_user()
    role = experience(user, "Captain", bullets=["Led the migration."])
    assert chosen(user, behavioral("leadership")).id == role

    review_edit(user, "experiences", role, {"bullets": ["Mentored two students."]})

    assert chosen(user, behavioral("leadership")) is None
    assert chosen(user, behavioral("mentorship")).id == role


def test_renaming_work_keeps_its_tags(seeded):
    user = new_user()
    item = project(user, "Release", [], "Shipped it.", competency_tags=["ownership"])

    review_edit(user, "projects", item, {"name": "Big release"})

    assert row(Project, item).competency_tags == ["ownership"]


# --- topics and the outline's general questions -----------------------------

def test_a_topic_question_gets_work_that_mentions_the_topic(seeded):
    user = new_user()
    project(user, "Other", [], "Built a form.")
    wanted = project(user, "Feed", [], "Drew the pages.\nAdded rate-limiting to the API.")

    found = chosen(user, topic_question("Rate limiting"))

    assert found == QuestionEvidence(kind="project", id=wanted, bullet=1)


def test_a_topic_named_among_the_technologies_counts(seeded):
    user = new_user()
    listed = project(user, "Feed", ["Caching"], "Drew the pages.")

    found = chosen(user, topic_question("Caching"))

    assert (found.id, found.bullet) == (listed, None)


def test_a_topic_nothing_mentions_is_left_empty_however_strong_the_work(seeded):
    user = new_user()
    experience(user, "Captain", bullets=["Architected and optimized the platform."])

    assert chosen(user, topic_question("Payment compliance", category="role_specific")) is None


def test_the_general_design_question_gets_work_with_technical_depth(seeded):
    user = new_user()
    deep = experience(user, "Engineer", bullets=["Architected the ingestion service."])

    found = chosen(user, topic_question("System design and trade-offs"))

    assert (found.id, found.competencies, found.bullet) == (deep, ["technical_depth"], 0)


# --- LeetCode ---------------------------------------------------------------

def test_practice_is_offered_when_no_work_shows_the_skill(seeded):
    user = new_user()
    solved(user, dynamic_programming=12, array=2)

    found = chosen(user, skill_question("dynamic_programming"))

    assert found == QuestionEvidence(kind="leetcode_topic", topic="dynamic-programming",
                                     skills=["dynamic_programming"])


def test_work_comes_before_practice(seeded):
    user = new_user()
    solved(user, dynamic_programming=90)
    wanted = project(user, "Solver", [], "Used dynamic programming to plan routes.")

    assert chosen(user, skill_question("dynamic_programming")).id == wanted


def test_a_couple_of_solved_problems_are_not_enough(seeded):
    user = new_user()
    solved(user, dynamic_programming=2)

    assert chosen(user, skill_question("dynamic_programming")) is None


@pytest.mark.parametrize("tags,topic", [
    ({"dynamic_programming": 20, "greedy": 8, "binary_search": 5}, "dynamic-programming"),
    ({"dynamic_programming": 25}, None),  # one topic isn't breadth
    ({"dynamic_programming": 4, "greedy": 4, "binary_search": 4}, None),  # too few problems
])
def test_algorithms_need_practice_across_topics(seeded, tags, topic):
    user = new_user()
    solved(user, **tags)

    found = chosen(user, skill_question("algorithms"))

    assert (found and found.topic) == topic


def test_a_topic_that_is_a_practice_topic_is_matched(seeded):
    user = new_user()
    solved(user, backtracking=9)

    assert chosen(user, topic_question("Backtracking", category="role_specific")).topic == "backtracking"


# --- saved kits -------------------------------------------------------------

def generate_and_save(user, job_id):
    async def go(db):
        draft = await generate_interview_kit(db, user.id, uuid.UUID(job_id))
        return draft, await save_new_kit(db, user.id, uuid.UUID(job_id), draft)
    return run(go)


def stale(user, kit) -> bool:
    async def go(db):
        return await evidence_is_stale(db, user.id, kit)
    return run(go)


def touch(user):
    async def go(db):
        await touch_evidence(db, user.id)
    run(go)


def remap(user, job_id, version=None):
    async def go(db):
        return await remap_kit(db, user.id, uuid.UUID(job_id), version)
    return run(go)


def postgres_question(saved):
    return next(q for q in saved.questions if q.topic == "PostgreSQL")


def test_a_generated_kit_is_matched_and_saved_with_its_evidence(seeded):
    user = new_user()
    wanted = experience(user, "Captain", bullets=["Led the Postgres migration."])
    job = add_job(user, [POSTGRES])

    draft, saved = generate_and_save(user, job)

    assert [q.thin_evidence for q in draft.questions] == [not q.evidence_refs for q in draft.questions]
    assert {q.thin_evidence for q in draft.questions} == {True, False}
    stored = postgres_question(saved)
    assert (stored.evidence_refs[0]["id"], stored.evidence_refs[0]["bullet"], stored.thin_evidence) == (
        str(wanted), 0, False)
    assert [[QuestionEvidence.model_validate(r) for r in q.evidence_refs] for q in saved.questions] == [
        q.evidence_refs for q in draft.questions]
    assert saved.kit.evidence_mapped_at == draft.evidence_mapped_at
    assert not stale(user, saved.kit)


def test_new_evidence_makes_a_kit_stale_until_it_is_matched_again(seeded):
    user = new_user()
    job = add_job(user, [POSTGRES])
    _draft, saved = generate_and_save(user, job)
    before = [(q.id, q.text) for q in saved.questions]
    assert postgres_question(saved).thin_evidence

    wanted = project(user, "Ledger", ["Postgres"], "Stores accounts in Postgres.")
    touch(user)
    assert stale(user, saved.kit)

    again = remap(user, job)

    assert [(q.id, q.text) for q in again.questions] == before  # the questions stay
    stored = run(lambda db: get_kit(db, user.id, uuid.UUID(job)))
    assert postgres_question(stored).evidence_refs[0]["id"] == str(wanted)
    assert postgres_question(stored).thin_evidence is False
    assert not stale(user, stored.kit)
    assert stored.kit.version == 1


def test_removed_evidence_empties_the_question_again(seeded):
    user = new_user()
    item = project(user, "Ledger", ["Postgres"], "Stores accounts in Postgres.")
    job = add_job(user, [POSTGRES])
    generate_and_save(user, job)

    async def hide(db):
        (await db.get(Project, item)).is_hidden = True
        await db.commit()
    run(hide)
    again = remap(user, job)

    assert (postgres_question(again).evidence_refs, postgres_question(again).thin_evidence) == ([], True)


def test_a_kit_never_matched_counts_as_stale(seeded):
    user = new_user()
    job = add_job(user, [POSTGRES])
    _draft, saved = generate_and_save(user, job)
    saved.kit.evidence_mapped_at = None

    assert stale(user, saved.kit)


def test_another_users_kit_cannot_be_matched_again(seeded):
    owner, other = new_user(), new_user()
    job = add_job(owner, [POSTGRES])
    generate_and_save(owner, job)

    assert remap(other, job) is None
    assert remap(owner, job, version=2) is None
    assert remap(owner, job).kit.version == 1
