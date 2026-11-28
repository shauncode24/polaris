"""The structure of a tailored resume: every claim names its evidence, and only
approved wording appears.
"""
import uuid

import pytest
from pydantic import ValidationError

from app.schemas.resume.tailored import (
    ExperienceEntry,
    Header,
    ProjectEntry,
    ResumeLine,
    SkillEntry,
    SourceRef,
    TailoredResumeDocument,
)


def source(kind="experience", **extra) -> dict:
    return {"kind": kind, "id": str(uuid.uuid4()), **extra}


def line(**extra) -> ResumeLine:
    return ResumeLine(**{"original": "Built an API.", "sources": [source()], **extra})


def document(**extra) -> TailoredResumeDocument:
    return TailoredResumeDocument(header=Header(full_name="Sam Rivera"), **extra)


@pytest.mark.parametrize("fields, shown", [
    ({}, "Built an API."),
    ({"rewrite": "Designed a REST API."}, "Built an API."),  # not yet approved
    ({"rewrite": "Designed a REST API.", "decision": "accepted"}, "Designed a REST API."),
    ({"rewrite": "Designed a REST API.", "decision": "rejected"}, "Built an API."),
    ({"rewrite": "Designed a REST API.", "decision": "accepted", "edited": " My words. "}, "My words."),
    ({"edited": "   "}, "Built an API."),
    ({"original": None, "rewrite": "A summary."}, ""),
    ({"original": None, "rewrite": "A summary.", "decision": "accepted"}, "A summary."),
])
def test_only_approved_wording_appears(fields, shown):
    assert line(**fields).text == shown


@pytest.mark.parametrize("build", [
    lambda: ResumeLine(original="Built an API.", sources=[]),
    lambda: ResumeLine(original="Built an API."),
    lambda: ExperienceEntry(role="Engineer", company="Acme", sources=[]),
    lambda: ProjectEntry(name="Ledger"),
    lambda: SkillEntry(name="Python", canonical="python", sources=[]),
], ids=["line, empty", "line, none", "experience", "project", "skill"])
def test_nothing_can_be_stated_without_a_source(build):
    with pytest.raises(ValidationError):
        build()


@pytest.mark.parametrize("fields", [
    {"original": None}, {"original": "  "}, {"original": "", "rewrite": " ", "edited": ""},
])
def test_a_line_needs_text(fields):
    with pytest.raises(ValidationError, match="needs some text"):
        line(**fields)


def test_a_source_names_its_row_except_for_leetcode_practice():
    assert SourceRef(kind="leetcode_tag").id is None
    with pytest.raises(ValidationError, match="needs the id"):
        SourceRef(kind="project")
    with pytest.raises(ValidationError):
        SourceRef(kind="rumour", id=uuid.uuid4())


def test_lines_are_found_wherever_they_are():
    resume = document(
        summary=line(id="s"),
        experience=[{"role": "Engineer", "company": "Acme", "sources": [source()], "bullets": [line(id="a")]}],
        projects=[{"name": "Ledger", "sources": [source("project")], "bullets": [line(id="b")]}],
        education=[{"institution": "State", "sources": [source("education")], "bullets": [line(id="c")]}],
    )
    assert [entry.id for entry in resume.lines()] == ["s", "a", "b", "c"]


def test_two_lines_cannot_share_an_id():
    with pytest.raises(ValidationError, match="same id"):
        document(
            summary=line(id="x"),
            projects=[{"name": "Ledger", "sources": [source("project")], "bullets": [line(id="x")]}],
        )


def test_new_lines_get_their_own_ids():
    assert line().id != line().id


def test_sections_can_be_reordered_but_not_lost_or_repeated():
    assert document().section_order == ["summary", "experience", "projects", "education", "skills"]
    order = ["skills", "projects", "experience", "education", "summary"]
    assert document(section_order=order).section_order == order

    for wrong in (order[:-1], order + ["skills"], order[:-1] + ["hobbies"]):
        with pytest.raises(ValidationError):
            document(section_order=wrong)


def test_it_survives_being_saved_as_json():
    resume = document(
        summary=line(rewrite="Backend engineer.", decision="accepted", flags=["'engineer' is unsupported"]),
        skills=[{"name": "Algorithms", "canonical": "algorithms", "sources": [{"kind": "leetcode_tag"}]}],
    )

    saved = resume.model_dump(mode="json")

    assert saved["summary"]["text"] == "Backend engineer."  # for the page that shows it
    assert TailoredResumeDocument.model_validate(saved) == resume
    # The text is always worked out again, never trusted from what was sent.
    saved["summary"]["text"] = "Ten years at a famous company."
    assert TailoredResumeDocument.model_validate(saved).summary.text == "Backend engineer."
