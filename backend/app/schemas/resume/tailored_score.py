from datetime import datetime

from pydantic import BaseModel


class KeywordCoverage(BaseModel):
    """Which of the job's required and implied skills the text names, as the
    job words them.
    """
    matched: list[str]
    missing: list[str]
    total: int
    percentage: int


class AtsWarning(BaseModel):
    type: str
    severity: str  # "high" | "medium" | "low"
    detail: str


class ScoreCard(BaseModel):
    ats_score: int  # out of 100
    parts: dict[str, int]  # the checks the score is made of, each out of 100
    warnings: list[AtsWarning]
    keywords: KeywordCoverage | None  # None when the job lists no skills


class UploadedResume(BaseModel):
    filename: str | None
    uploaded_at: datetime


class ResumeScore(BaseModel):
    after: ScoreCard  # the tailored resume as it reads now
    before: ScoreCard | None = None  # the latest uploaded resume
    uploaded: UploadedResume | None = None
