"""What to study for one job: its gaps, the LeetCode topics that help close
them, and the interview questions they affect.
"""
import uuid
from typing import Literal

from pydantic import BaseModel

from app.schemas.interview.kit import QuestionCategory
from app.schemas.skill_gap.skill_gap import Severity


class LeetcodeTopic(BaseModel):
    topic: str
    url: str
    solved: int | None = None  # None until LeetCode has been synced


class StudyQuestion(BaseModel):
    question_id: uuid.UUID
    text: str
    latest_score: float | None = None  # of the newest practice that was scored


class StudyGap(BaseModel):
    """One of the job's skills the user's record doesn't yet show well."""
    skill: str  # canonical name
    name: str  # as the job writes it
    status: Literal["missing", "partial"]
    severity: Severity
    requirement: str  # "required" | "implicit" | "nice_to_have"
    why: str
    action: str
    leetcode: list[LeetcodeTopic] = []  # least practised first; none if LeetCode doesn't cover it
    questions: list[StudyQuestion] = []  # the interview kit's questions about it


class StudyPlan(BaseModel):
    job_intelligence_id: uuid.UUID
    role: str | None = None
    company: str | None = None
    gaps: list[StudyGap] = []  # the most pressing first
    unanswered: list[StudyQuestion] = []  # other questions with no example to answer from
    weak: list[StudyQuestion] = []  # questions practised and answered poorly
    weakest_category: QuestionCategory | None = None
    kit_version: int | None = None  # none when the job has no interview kit
    notes: list[str] = []  # what would make this plan fuller or more current
