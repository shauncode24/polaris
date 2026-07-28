from datetime import datetime

from pydantic import BaseModel


class SkillDelta(BaseModel):
    skill: str
    previous_confidence: float | None = None
    current_confidence: float
    delta: float


class EvolutionReport(BaseModel):
    has_previous: bool
    previous_snapshot_at: datetime | None = None
    current_snapshot_at: datetime | None = None
    skills_gained: list[str] = []
    skills_lost: list[str] = []
    skills_strengthened: list[SkillDelta] = []
    skills_weakened: list[SkillDelta] = []
    summary: str = ""