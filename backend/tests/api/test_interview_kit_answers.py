"""The answer outline for each interview question: the user's own words under the
headings of a good answer. Real database; no model.
"""
import uuid
from datetime import date, datetime, timezone

import pytest

from app.core import llm
from app.models.facts import Experience, LeetcodeSnapshot
from app.models.inference import ProjectClaimAuditReview
from app.models.interview_kit import InterviewQuestion
from app.schemas.interview.kit import AnswerOutline, InterviewKitDraft
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.services.evidence.review import apply_review
from app.services.evidence.state import touch_evidence
from app.services.interview.kit_answers import answer_outlines
from app.services.interview.kit_evidence import map_evidence, remap_kit
from app.services.interview.kit_store import save_new_kit
from tests.api.test_evidence import run
from tests.api.test_interview_kit_evidence import behavioral, hide_skill, skill_question, solved, topic_question
from tests.api.test_resume_rewriting import POSTGRES, add_job
from tests.api.test_resume_selection import experience, new_user, project, repo, upload
from tests.llm_stub import model  # noqa: F401 (model is a fixture)

NOW = datetime.now(timezone.utc)


def kit_for(user, *questions, matched=True) -> str:
    """Saves a kit of these questions, matched to the user's work as generation
    would, and returns its job.
    """
    job_id = add_job(user, [POSTGRES])

    async def go(db):
        draft = InterviewKitDraft(seniority="mid", questions=list(questions))
        if matched:
            mapping = await map_evidence(db, user.id, JobIntelligenceProfile(), list(questions))
            draft = draft.model_copy(update={
                "evidence_mapped_at": mapping.mapped_at,
                "evidence_notice": mapping.notice,
                "questions": [q.model_copy(update={"evidence_refs": refs, "thin_evidence": not refs})
                              for q, refs in zip(questions, mapping.refs)],
            })
        await save_new_kit(db, user.id, uuid.UUID(job_id), draft)

    run(go)
    return job_id


def outlines(user, job_id, version=None):
    async def go(db):
        return await answer_outlines(db, user.id, uuid.UUID(job_id), version)
    return run(go)


def outline(user, question) -> AnswerOutline:
    return outlines(user, kit_for(user, question)).outlines[0]


def placed(found: AnswerOutline) -> dict[str, list[str]]:
    """heading -> the facts under it, for the headings that have any."""
    return {s.heading: [f.text for f in s.facts] for s in found.sections if s.facts}


def headings(found: AnswerOutline) -> list[str]:
    return [s.heading for s in found.sections]


def others(found: AnswerOutline) -> list[str]:
    return [f.text for f in found.other_facts]


def edit(user, kind, item_id, fields):
    async def go(db):
        await apply_review(db, user.id, kind, item_id, "edit", fields)
    run(go)


def hide(user, table, item_id):
    async def go(db):
        (await db.get(table, item_id)).is_hidden = True
        await db.commit()
    run(go)


# --- placing the user's words -----------------------------------------------

def test_the_lines_that_show_the_skill_are_what_you_did_in_your_own_words(seeded):
    user = new_user()
    role = experience(user, "Backend Intern", ["Python"], [
        "Wrote the handover notes.", "Tuned Postgres queries for the order page.",
    ], company="Northwind", start_date=date(2025, 5, 1), start_date_text="May 2025", end_date_text="Aug 2025")

    found = outline(user, skill_question("postgres"))

    assert placed(found) == {
        "Context": ["Backend Intern at Northwind (May 2025 - Aug 2025)"],
        "What you did": ["Tuned Postgres queries for the order page."],
    }
    assert others(found) == ["Wrote the handover notes."]
    assert [(f.text, f.bullet) for f in found.sections[2].facts] == [
        ("Tuned Postgres queries for the order page.", 1)]
    assert (found.story.kind, found.story.id, found.story.title, found.story.period, found.story.technologies) == (
        "experience", role, "Backend Intern at Northwind", "May 2025 - Aug 2025", ["Python"])
    assert found.warnings == []


def test_a_project_is_titled_by_its_name_with_its_link_and_technologies(seeded):
    user = new_user()
    repo(user, "ledger", ["Docker"])
    project(user, "Ledger", ["Postgres"], "- Stores accounts in Postgres.", github_repo_name="ledger")

    found = outline(user, skill_question("postgres"))

    assert placed(found) == {"Context": ["Ledger"], "What you did": ["Stores accounts in Postgres."]}
    assert (found.story.technologies, found.story.url, found.story.period) == (
        ["Postgres", "Docker"], "https://github.com/sam/ledger", None)


@pytest.mark.parametrize("line", [
    "Cut Postgres query time by 40%.",
    "Moved report time from 40s to 6s with a Postgres index.",
    "Made the Postgres nightly job 3x faster.",
    "Saved $2,000 a month on Postgres hosting.",
    "Reduced Postgres storage by 12 gigabytes.",
])
def test_a_line_stating_a_change_is_the_result_when_another_says_what_was_done(seeded, line):
    user = new_user()
    experience(user, "Engineer", bullets=["Rewrote the Postgres queries.", line])

    found = outline(user, skill_question("postgres"))

    assert placed(found)["What you did"] == ["Rewrote the Postgres queries."]
    assert placed(found)["Result"] == [line]


@pytest.mark.parametrize("line", [
    "Ran Postgres 16 in staging.",
    "Owned the Postgres roadmap from 2023 to 2024.",
    "Migrated Postgres by 2025.",
    "Answered questions from 30 students about Postgres.",
])
def test_a_number_that_measures_no_change_is_not_offered_as_a_result(seeded, line):
    user = new_user()
    experience(user, "Engineer", bullets=["Rewrote the Postgres queries.", line])

    assert "Result" not in placed(outline(user, skill_question("postgres")))


def test_a_single_line_stating_a_change_still_says_what_you_did(seeded):
    user = new_user()
    experience(user, "Engineer", bullets=["Cut Postgres query time by 40% with new indexes."])

    found = placed(outline(user, skill_question("postgres")))

    assert found["What you did"] == ["Cut Postgres query time by 40% with new indexes."]
    assert "Result" not in found


def test_a_figure_from_other_work_in_the_role_is_never_this_answers_result(seeded):
    user = new_user()
    experience(user, "Engineer", bullets=[
        "Backed up Postgres.", "Moved Postgres to new hosts.", "Cut page load time by 70% with image resizing.",
    ])

    found = outline(user, skill_question("postgres"))

    assert "Result" not in placed(found)
    assert others(found) == ["Cut page load time by 70% with image resizing."]


def test_a_skill_that_is_only_listed_places_no_line_and_says_so(seeded):
    user = new_user()
    project(user, "Tool", ["Postgres"], "A small tool.")

    found = outline(user, skill_question("postgres"))

    assert placed(found) == {"Context": ["Tool"]}
    assert others(found) == ["A small tool."]
    assert "only lists it" in found.warnings[0]


def test_a_behavioral_answer_places_the_lines_showing_the_competency(seeded):
    user = new_user()
    experience(user, "Captain", bullets=["Wrote the notes.", "Led the migration."], company="Club")

    found = outline(user, behavioral("leadership"))

    assert headings(found) == ["Situation", "Your task", "What you did", "Result", "What you learned"]
    assert placed(found) == {"Situation": ["Captain at Club"], "What you did": ["Led the migration."]}
    assert others(found) == ["Wrote the notes."]


def test_work_only_the_model_tagged_leaves_the_choice_of_line_to_the_user(seeded):
    user = new_user()
    project(user, "Release", [], "Saw the release through.", competency_tags=["ownership"])

    found = outline(user, behavioral("ownership"))

    assert placed(found) == {"Situation": ["Release"]}
    assert others(found) == ["Saw the release through."]
    assert "Pick it from the other lines" in found.warnings[0]


@pytest.mark.parametrize("question,expected", [
    (behavioral("conflict_resolution"),
     ["Situation", "The disagreement", "What you did", "How it was settled", "What you learned"]),
    (behavioral("failure_recovery"), ["Situation", "What went wrong", "What you did", "What changed afterwards"]),
    (skill_question("postgres"), ["Context", "The problem", "What you did", "Decisions and trade-offs", "Result",
                                  "What you would change"]),
    (topic_question("Caching"), ["Context", "Requirements", "How you would build it", "Trade-offs",
                                 "What breaks first"]),
])
def test_each_kind_of_question_has_its_own_headings(seeded, question, expected):
    assert headings(outline(new_user(), question)) == expected


def test_a_topic_answer_places_the_lines_naming_the_topic(seeded):
    user = new_user()
    project(user, "Feed", [], "Drew the pages.\nAdded caching to the feed.")

    found = outline(user, topic_question("Caching"))

    assert placed(found) == {"Context": ["Feed"], "How you would build it": ["Added caching to the feed."]}


# --- practice ---------------------------------------------------------------

def test_practice_is_stated_as_counts_and_not_as_work(seeded):
    user = new_user()
    solved(user, dynamic_programming=12)

    found = outline(user, skill_question("dynamic_programming"))

    assert found.story.kind == "leetcode"
    assert placed(found) == {
        "What you have practised": ["12 problems solved on LeetCode in dynamic programming"]}
    assert "not that you used this at work" in found.warnings[0]


def test_algorithm_practice_lists_the_topics_behind_it(seeded):
    user = new_user()
    solved(user, dynamic_programming=20, greedy=8, binary_search=5)

    found = placed(outline(user, skill_question("algorithms")))

    assert found["What you have practised"] == [
        "20 problems solved on LeetCode in dynamic programming",
        "8 problems solved on LeetCode in greedy",
        "5 problems solved on LeetCode in binary search",
    ]


def test_practice_the_latest_sync_no_longer_shows_is_not_claimed(seeded):
    user = new_user()
    solved(user, dynamic_programming=12)
    job = kit_for(user, skill_question("dynamic_programming"))

    async def later(db):
        db.add(LeetcodeSnapshot(user_id=user.id, tag="dynamic-programming", solved_count=0,
                                pulled_at=datetime.now(timezone.utc)))
        await db.commit()
    run(later)
    found = outlines(user, job).outlines[0]

    assert (found.story, placed(found)) == (None, {})
    assert "removed or hidden" in found.warnings[0]


# --- nothing to say, and warnings -------------------------------------------

def test_a_thin_question_gets_headings_and_no_story(seeded):
    found = outline(new_user(), skill_question("postgres"))

    assert (found.story, placed(found), found.other_facts) == (None, {}, [])
    assert all(s.prompt for s in found.sections)
    assert "Nothing in your record" in found.warnings[0]


def test_work_that_could_not_be_checked_is_not_called_missing(seeded, model, monkeypatch):
    user = new_user()
    project(user, "Release", [], f"Saw the release through, {uuid.uuid4().hex}.")
    monkeypatch.setattr(llm, "API_KEY", "")

    behaving, technical = outlines(user, kit_for(user, behavioral("ownership"), skill_question("postgres"))).outlines

    assert "not all of it could be checked" in behaving.warnings[0]
    assert "Nothing in your record" in technical.warnings[0]  # skills need no tagging


def test_a_question_never_matched_says_so(seeded):
    user = new_user()
    project(user, "Ledger", ["Postgres"], "Stores accounts in Postgres.")

    result = outlines(user, kit_for(user, skill_question("postgres"), matched=False))

    assert result.stale
    assert result.outlines[0].story is None
    assert "hasn't been matched" in result.outlines[0].warnings[0]


def test_unsupported_claims_found_in_the_project_are_named(seeded):
    user = new_user()
    item = project(user, "Ledger", ["Postgres"], "Stores accounts in Postgres.")

    async def audit(db):
        db.add(ProjectClaimAuditReview(user_id=user.id, project_id=item, report_json={
            "narrative": {"risk_level": "high"}, "facts": {"unsupported_claims": ["Kafka", "Redis"]}}))
        await db.commit()
    run(audit)

    found = outline(user, skill_question("postgres"))

    assert "claims its code doesn't support: Kafka; Redis." in found.warnings[0]


# --- the record as it is now ------------------------------------------------

def test_an_outline_follows_the_wording_as_it_is_now(seeded):
    user = new_user()
    item = project(user, "Ledger", [], "Stores accounts in Postgres.")
    job = kit_for(user, skill_question("postgres"))

    edit(user, "projects", item, {"description": "Added a form.\nKeeps balances in Postgres."})
    result = outlines(user, job)

    assert result.stale
    assert placed(result.outlines[0])["What you did"] == ["Keeps balances in Postgres."]
    assert others(result.outlines[0]) == ["Added a form."]


def test_work_that_no_longer_shows_the_subject_is_not_offered(seeded):
    user = new_user()
    item = project(user, "Ledger", [], "Stores accounts in Postgres.")
    story = experience(user, "Captain", bullets=["Led the migration."])
    topical = project(user, "Feed", [], "Added caching.")
    job = kit_for(user, skill_question("postgres"), behavioral("leadership"), topic_question("Caching"))

    edit(user, "projects", item, {"description": "Stores accounts in files."})
    edit(user, "experiences", story, {"bullets": ["Wrote notes."]})

    async def retag(db):  # as the next matching would
        (await db.get(Experience, story)).competency_tags = []
        await db.commit()
    run(retag)
    edit(user, "projects", topical, {"description": "Added a form."})
    found = outlines(user, job).outlines

    assert [o.story for o in found] == [None, None, None]
    assert all("no longer shows" in o.warnings[0] for o in found)


@pytest.mark.parametrize("remove", ["hide the item", "hide the skill", "replace it with a newer upload"])
def test_removed_evidence_leaves_the_outline_at_once(seeded, remove):
    user = new_user()
    old = upload(user, days_ago=30)
    role = experience(user, "Engineer", bullets=["Tuned Postgres."], resume_id=old, days_ago=30)
    job = kit_for(user, skill_question("postgres"))
    assert outlines(user, job).outlines[0].story.id == role

    if remove == "hide the item":
        hide(user, Experience, role)
    elif remove == "hide the skill":
        hide_skill(user, "postgres")
    else:
        experience(user, "Engineer", bullets=["Tuned Postgres again."], resume_id=upload(user))
    found = outlines(user, job).outlines[0]

    assert (found.story, placed(found), found.other_facts) == (None, {}, [])
    assert "removed or hidden" in found.warnings[0]


def test_hidden_practice_and_a_hidden_skill_among_the_technologies_are_left_out(seeded):
    user = new_user()
    solved(user, dynamic_programming=12)
    project(user, "Ledger", ["Postgres", "Redis"], "Stores accounts in Postgres.")
    job = kit_for(user, skill_question("dynamic_programming"), skill_question("postgres"))

    hide_skill(user, "dynamic_programming")
    hide_skill(user, "redis")
    practice, work = outlines(user, job).outlines

    assert (practice.story, placed(practice)) == (None, {})
    assert work.story.technologies == ["Postgres"]


def test_the_newest_copy_of_a_role_is_used_even_when_only_the_older_has_no_dates(seeded):
    user = new_user()
    experience(user, "Engineer", bullets=["Ran Postgres the old way."], resume_id=upload(user, days_ago=30),
               days_ago=30)
    newest = experience(user, "Engineer", bullets=["Ran Postgres the new way."], resume_id=upload(user),
                        start_date=date(2024, 1, 1))

    found = outline(user, skill_question("postgres"))

    assert found.story.id == newest
    assert placed(found)["What you did"] == ["Ran Postgres the new way."]


def test_matching_again_brings_a_kit_up_to_date(seeded):
    user = new_user()
    job = kit_for(user, skill_question("postgres"))
    project(user, "Ledger", ["Postgres"], "Stores accounts in Postgres.")

    async def go(db):
        await touch_evidence(db, user.id)
        await remap_kit(db, user.id, uuid.UUID(job))
    run(go)
    result = outlines(user, job)

    assert not result.stale
    assert result.outlines[0].story.title == "Ledger"


# --- whose, and at what cost ------------------------------------------------

def test_outlines_come_in_the_kits_order_for_the_version_asked(seeded):
    user = new_user()
    project(user, "Ledger", ["Postgres"], "Stores accounts in Postgres.")
    job = kit_for(user, behavioral("ownership"), skill_question("postgres"))

    async def go(db):
        await save_new_kit(db, user.id, uuid.UUID(job), InterviewKitDraft(
            seniority="mid", questions=[skill_question("postgres")]))
    run(go)

    async def ids(db):
        from sqlalchemy import select
        rows = await db.scalars(select(InterviewQuestion.id).order_by(InterviewQuestion.position))
        return list(rows)

    first = outlines(user, job, 1)
    assert (first.version, len(first.outlines)) == (1, 2)
    assert first.outlines[1].story.title == "Ledger"
    assert {o.question_id for o in first.outlines} <= set(run(ids))
    assert outlines(user, job).version == 2
    assert outlines(user, job, 3) is None


def test_another_users_kit_gives_nothing(seeded):
    owner, other = new_user(), new_user()
    job = kit_for(owner, skill_question("postgres"))

    assert outlines(other, job) is None
    assert outlines(owner, job) is not None


def test_a_reference_to_another_users_work_shows_none_of_it(seeded):
    owner, other = new_user(), new_user()
    theirs = project(owner, "Secret", ["Postgres"], "Stores secrets in Postgres.")
    question = skill_question("postgres", evidence_refs=[{"kind": "project", "id": theirs, "skills": ["postgres"]}],
                              thin_evidence=False)

    found = outlines(other, kit_for(other, question, matched=False)).outlines[0]

    assert (found.story, placed(found), found.other_facts) == (None, {}, [])


def test_no_model_is_called(seeded, model, monkeypatch):
    user = new_user()
    project(user, "Ledger", ["Postgres"], "Stores accounts in Postgres.")
    job = kit_for(user, skill_question("postgres"))
    experience(user, "Engineer", bullets=["Something no keyword reads."])  # untagged, so matching would ask
    monkeypatch.setattr(llm, "API_KEY", "test-key")
    model.requests.clear()

    outlines(user, job)

    assert model.requests == []
