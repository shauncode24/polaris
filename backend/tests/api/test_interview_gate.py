"""The truthfulness gate for answer outlines: for the resume gate's ten made-up
profile and job pairs, every statement on every outline is compared with the
database by a checker that shares no code with the outline builder.

The stand-in model claims every competency for every project and role, which
puts as much work as it can under the behavioral questions.
"""
import json
import re
import uuid

import pytest
from sqlalchemy import select

from app.core import llm
from app.models.facts import Experience, LeetcodeSnapshot, Project
from app.models.github_analysis import GithubProjectAnalysis
from app.schemas.interview.kit import KitOutlines
from app.services.interview.competency_tagging import CANONICAL_COMPETENCIES
from app.services.interview.kit_answers import answer_outlines
from app.services.interview.kit_generation import generate_interview_kit
from app.services.interview.kit_store import save_new_kit
from tests.api.resume_gate_profiles import PROFILES
from tests.api.test_evidence import run
from tests.api.test_interview_kit_evidence import solved
from tests.api.test_resume_gate import create
from tests.api.test_resume_rewriting import add_job
from tests.llm_stub import reply


@pytest.fixture(autouse=True)
def eager_model(monkeypatch):
    async def answer(**request):
        asked = json.loads(request["messages"][1]["content"])
        if isinstance(asked, list):  # competency tagging
            return reply({"results": [{"key": item["key"], "tags": sorted(CANONICAL_COMPETENCIES)}
                                      for item in asked]})
        return reply({"questions": [
            {"id": q["id"], "question": f"How did you lead the {q['topic']} work at Google?"}
            for q in asked["questions"]
        ]})

    monkeypatch.setattr(llm, "API_KEY", "test-key")
    monkeypatch.setattr(llm, "chat_completion", answer)


def create_with_practice(profile):
    user = create(profile)
    if profile.leetcode:
        solved(user, dynamic_programming=40, greedy=20, binary_search=25, array=30, tree=15, graph=12)
    return user


def build(user, job_id) -> KitOutlines:
    async def go(db):
        draft = await generate_interview_kit(db, user.id, uuid.UUID(job_id))
        await save_new_kit(db, user.id, uuid.UUID(job_id), draft)
        return await answer_outlines(db, user.id, uuid.UUID(job_id))
    return run(go)


def record(user_id) -> dict:
    """The user's visible evidence, read straight from the tables."""
    async def go(db):
        async def rows(table):
            found = (await db.scalars(select(table).where(table.user_id == user_id))).all()
            return {r.id: r for r in found if not getattr(r, "is_hidden", False)}
        return {
            "experience": await rows(Experience), "project": await rows(Project),
            "repo": await rows(GithubProjectAnalysis), "practice": await rows(LeetcodeSnapshot),
        }
    return run(go)


def lines_of(kind, row) -> list[str]:
    texts = row.bullets or [] if kind == "experience" else (row.description or "").split("\n")
    return [re.sub(r"^\s*[-*•]\s+", "", text or "").strip() for text in texts]


def unsupported(user_id, result: KitOutlines) -> list[str]:
    """Every fact, title, date, technology or link on an outline that the user's
    record doesn't bear out.
    """
    held, found = record(user_id), []

    def wrong(what: str, condition: bool):
        if not condition:
            found.append(what)

    for outline in result.outlines:
        facts = [f for s in outline.sections for f in s.facts] + outline.other_facts
        story = outline.story
        if story is None:
            wrong("facts with no story", not facts)
        elif story.kind == "leetcode":
            for fact in facts:
                counted = re.fullmatch(r"(\d+) problems? solved on LeetCode in (.+)", fact.text)
                wrong(f"practice: {fact.text}", counted is not None and any(
                    row.tag.replace("-", " ") == counted[2] and row.solved_count == int(counted[1])
                    for row in held["practice"].values()))
        else:
            row = held[story.kind].get(story.id)
            if row is None:
                found.append(f"story {story.title} is not a visible row of the user's")
                continue
            title = f"{row.role} at {row.company}" if story.kind == "experience" else row.name
            wrong(f"title {story.title}", story.title == title)
            written = " - ".join(filter(None, [row.start_date_text, row.end_date_text])) \
                if story.kind == "experience" else ""
            wrong(f"period {story.period}", (story.period or "") == written)
            repo = next((r for r in held["repo"].values()
                         if story.kind == "project" and r.repo_name == row.github_repo_name), None)
            listed = {*(row.stack or []), *((repo.technologies or []) if repo else [])}
            wrong(f"technologies {story.technologies}", set(story.technologies) <= listed)
            links = {None} if story.kind == "experience" else {row.repo_url, repo.html_url if repo else None}
            wrong(f"link {story.url}", story.url in links)
            headline = f"{title} ({written})" if written else title
            for fact in facts:
                if fact.bullet is None:
                    wrong(f"heading fact: {fact.text}", fact.text == headline)
                else:
                    lines = lines_of(story.kind, row)
                    wrong(f"line: {fact.text}", fact.bullet < len(lines) and lines[fact.bullet] == fact.text)
    return found


def test_no_outline_states_anything_the_record_does_not(seeded):
    failures, kinds, thin, placed, apart = {}, set(), 0, 0, 0

    for profile in PROFILES:
        user = create_with_practice(profile)
        job = add_job(user, profile.job, nice=profile.nice)

        result = build(user, job)
        found = unsupported(user.id, result)

        if found:
            failures[profile.key] = found
        kinds |= {o.story.kind for o in result.outlines if o.story}
        thin += sum(o.story is None for o in result.outlines)
        placed += sum(f.bullet is not None for o in result.outlines for s in o.sections for f in s.facts)
        apart += sum(len(o.other_facts) for o in result.outlines)

    assert failures == {}
    # The pairs exercise every kind of story, and answers without one.
    assert kinds == {"project", "experience", "leetcode"}
    assert thin > 10 and placed > 10 and apart > 40, (thin, placed, apart)


def test_the_checker_notices_a_statement_the_record_does_not_make(seeded):
    profile = PROFILES[0]
    user = create(profile)
    result = build(user, add_job(user, profile.job, nice=profile.nice))
    assert unsupported(user.id, result) == []
    outline = next(o for o in result.outlines if any(f.bullet is not None for s in o.sections for f in s.facts))
    fact = next(f for s in outline.sections for f in s.facts if f.bullet is not None)
    fact.text = fact.text.rstrip(".") + ", leading a team."
    outline.story.technologies.append("Kafka")

    assert len(unsupported(user.id, result)) == 2
