"""The interview kit for one job: its practice questions, by category.

What a question is about (category, topic, skills, competencies) is decided
from the job without a model (services/interview/kit_outline.py). A model only
words the question. Which of the user's work answers it is then matched without
a model's judgement (services/interview/kit_evidence.py).
"""
import uuid
from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.interview.competency_tagging import CANONICAL_COMPETENCIES

QuestionCategory = Literal["technical_depth", "system_design", "behavioral", "role_specific"]
CATEGORIES: tuple[QuestionCategory, ...] = get_args(QuestionCategory)
# "model": worded by the model. "outline": the standard wording.
QuestionOrigin = Literal["model", "outline"]

MAX_QUESTION_LENGTH = 400


class QuestionEvidence(BaseModel):
    """One piece of the user's record that can answer a question, and why."""
    kind: Literal["project", "experience", "leetcode_topic"]
    id: uuid.UUID | None = None  # the project or role
    topic: str | None = None  # the LeetCode tag
    bullet: int | None = Field(default=None, ge=0)  # the row's line that shows it, if one does
    skills: list[str] = []  # the question's skills it shows
    competencies: list[str] = []  # the question's competencies it shows

    @model_validator(mode="after")
    def _points_at_something(self):
        if self.kind == "leetcode_topic":
            if not self.topic:
                raise ValueError("LeetCode evidence needs its topic")
        elif self.id is None:
            raise ValueError(f"'{self.kind}' evidence needs the id of its row")
        return self


class KitQuestion(BaseModel):
    category: QuestionCategory
    topic: str = Field(min_length=1)  # what it is about, in the job's words where it has them
    text: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)
    skills: list[str] = []  # the job's skills it is about, by canonical name
    competencies: list[str] = []  # what answering it should show
    origin: QuestionOrigin = "outline"
    evidence_refs: list[QuestionEvidence] = []  # the best the user has, if any
    thin_evidence: bool | None = None  # None until matched against the record

    @field_validator("competencies")
    @classmethod
    def _known_competencies(cls, value: list[str]) -> list[str]:
        unknown = set(value) - CANONICAL_COMPETENCIES
        if unknown:
            raise ValueError(f"unknown competencies: {', '.join(sorted(unknown))}")
        return value


class InterviewKitDraft(BaseModel):
    """A generated kit that has not been saved."""
    seniority: str
    questions: list[KitQuestion] = Field(min_length=1)
    notice: str | None = None  # why some or all questions have the standard wording; safe to show
    evidence_mapped_at: datetime | None = None  # when the record was read to match it
    evidence_notice: str | None = None  # what the matching couldn't check; safe to show


class OutlineStory(BaseModel):
    """The work an answer is built on."""
    kind: Literal["project", "experience", "leetcode"]
    id: uuid.UUID | None = None  # the project or role
    title: str
    period: str | None = None  # as the record words it
    technologies: list[str] = []
    url: str | None = None


class OutlineFact(BaseModel):
    """Something the record says, in its own words."""
    text: str
    bullet: int | None = None  # which of the story's lines it is, if one


class OutlineSection(BaseModel):
    heading: str
    prompt: str  # what to cover here; says nothing about the user
    facts: list[OutlineFact] = []  # empty when the record says nothing for it


class AnswerOutline(BaseModel):
    """How to answer one question from the user's own record."""
    question_id: uuid.UUID
    story: OutlineStory | None = None  # none when there is no evidence
    sections: list[OutlineSection]
    other_facts: list[OutlineFact] = []  # the rest of the story, placed under no heading
    warnings: list[str] = []


class KitOutlines(BaseModel):
    version: int
    stale: bool  # the evidence has changed since it was matched
    outlines: list[AnswerOutline]  # in the kit's order


class WordedQuestion(BaseModel):
    id: str
    question: str


class QuestionWordingReply(BaseModel):
    """What the model sends back."""
    questions: list[WordedQuestion]
