"""Responses for the job library: comparing saved jobs side by side."""
from typing import Literal

from pydantic import BaseModel

from app.schemas.skill_gap.interpretation import OverallMatch


class ComparedJob(BaseModel):
    id: str
    role: str | None = None
    company: str | None = None
    seniority_level: str = "unspecified"
    is_primary: bool = False
    # None when no skills were extracted, so there is nothing to score.
    overall_match: OverallMatch | None = None


class ComparedSkill(BaseModel):
    skill: str
    # The user's standing on this skill, which is the same for every job.
    status: Literal["have", "partial", "missing"]
    # job id -> how that job asks for it ("required" | "implicit" |
    # "nice_to_have"). A job that doesn't ask for it has no entry.
    bands: dict[str, str]


class JobComparison(BaseModel):
    jobs: list[ComparedJob]
    skills: list[ComparedSkill]
