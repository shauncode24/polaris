"""Practising an interview kit's questions: an answer, the feedback on it, and
how much of the kit has been covered.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.interview.kit import QuestionCategory

MIN_ANSWER_LENGTH = 20
MAX_ANSWER_LENGTH = 5000


class PracticeAnswer(BaseModel):
    answer: str

    @field_validator("answer")
    @classmethod
    def _worth_reviewing(cls, value: str) -> str:
        value = value.strip()
        if not MIN_ANSWER_LENGTH <= len(value) <= MAX_ANSWER_LENGTH:
            raise ValueError(f"An answer needs {MIN_ANSWER_LENGTH} to {MAX_ANSWER_LENGTH} characters.")
        return value


class HeadingFeedback(BaseModel):
    """One thing a good answer covers, and whether this one did."""
    heading: str
    prompt: str
    covered: bool | None = None  # None when the answer wasn't reviewed
    quote: str | None = None  # the answer's own words that cover it
    note: str | None = None


class AttemptFeedback(BaseModel):
    headings: list[HeadingFeedback]
    overall: str | None = None
    # What the answer states that the record doesn't show; found without a model.
    unrecorded_figures: list[str] = []
    unrecorded_technologies: list[str] = []
    warnings: list[str] = []
    notice: str | None = None  # why there is no review; safe to show


class PracticeAttemptView(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    answer: str
    created_at: datetime
    score: float | None = None  # share of the headings covered, 0 to 1
    feedback: AttemptFeedback


class QuestionProgress(BaseModel):
    question_id: uuid.UUID
    category: QuestionCategory
    topic: str
    text: str
    attempts: int
    latest_score: float | None = None  # of the newest attempt that was scored


class CategoryProgress(BaseModel):
    category: QuestionCategory
    total: int
    practised: int
    average_score: float | None = None  # over the questions that have a score


class KitProgress(BaseModel):
    version: int
    total: int
    practised: int
    weakest: QuestionCategory | None = None  # none until the categories differ
    categories: list[CategoryProgress]
    questions: list[QuestionProgress]  # in the kit's order


class HeadingVerdict(BaseModel):
    heading: str
    covered: bool
    quote: str = ""
    note: str = ""


class PracticeReviewReply(BaseModel):
    """What the model sends back."""
    headings: list[HeadingVerdict]
    overall: str = ""
