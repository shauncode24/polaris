from datetime import datetime

from pydantic import BaseModel


class SkillDelta(BaseModel):
    skill: str
    previous_confidence: float | None = None
    current_confidence: float
    delta: float


class WeeklyBriefFacts(BaseModel):
    previous_generated_at: datetime | None = None
    current_generated_at: datetime
    skills_strengthened: list[SkillDelta] = []
    skills_weakened: list[SkillDelta] = []
    resume_score_delta: float | None = None
    github_commits_delta: int | None = None
    github_new_repos: int = 0
    leetcode_solved_delta: int | None = None
    goals_progress: list[dict] = []


class WeeklyBriefLLMOutput(BaseModel):
    headline: str = ""
    whats_changed: list[str] = []
    biggest_leverage_move: str = ""


class WeeklyBriefReport(BaseModel):
    facts: WeeklyBriefFacts
    narrative: WeeklyBriefLLMOutput
    generated_at: datetime | None = None
    analysis_degraded: bool = False