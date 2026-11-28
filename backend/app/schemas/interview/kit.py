"""The interview kit for one job: its practice questions, by category.

What a question is about (category, topic, skills, competencies) is decided
from the job without a model (services/interview/kit_outline.py). A model only
words the question.
"""
from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator

from app.services.interview.competency_tagging import CANONICAL_COMPETENCIES

QuestionCategory = Literal["technical_depth", "system_design", "behavioral", "role_specific"]
CATEGORIES: tuple[QuestionCategory, ...] = get_args(QuestionCategory)
# "model": worded by the model. "outline": the standard wording.
QuestionOrigin = Literal["model", "outline"]

MAX_QUESTION_LENGTH = 400


class KitQuestion(BaseModel):
    category: QuestionCategory
    topic: str = Field(min_length=1)  # what it is about, in the job's words where it has them
    text: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)
    skills: list[str] = []  # the job's skills it is about, by canonical name
    competencies: list[str] = []  # what answering it should show
    origin: QuestionOrigin = "outline"

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


class WordedQuestion(BaseModel):
    id: str
    question: str


class QuestionWordingReply(BaseModel):
    """What the model sends back."""
    questions: list[WordedQuestion]
