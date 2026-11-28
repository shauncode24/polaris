"""What the interview kit page receives."""
from datetime import datetime

from pydantic import BaseModel

from app.schemas.interview.kit import AnswerOutline, QuestionCategory, QuestionOrigin
from app.schemas.interview.practice import CategoryProgress


class KitJob(BaseModel):
    id: str
    role: str | None = None
    company: str | None = None


class QuestionView(BaseModel):
    id: str
    category: QuestionCategory
    topic: str
    text: str
    origin: QuestionOrigin
    thin: bool | None = None  # None until matched against the record
    shows: list[str] = []  # what the matched work shows, in words for the user
    outline: AnswerOutline  # built from the record as it is now
    attempts: int = 0
    latest_score: float | None = None


class KitDetail(BaseModel):
    version: int
    created_at: datetime
    notice: str | None = None  # why some questions have the standard wording
    evidence_notice: str | None = None  # what the matching couldn't check
    stale: bool  # the evidence has changed since it was matched
    total: int
    practised: int
    weakest: QuestionCategory | None = None
    categories: list[CategoryProgress]
    questions: list[QuestionView]  # in the kit's order


class KitPage(BaseModel):
    job: KitJob
    versions: list[int]  # newest first
    kit: KitDetail | None = None  # none generated yet
