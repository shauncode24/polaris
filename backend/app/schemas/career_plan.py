from datetime import date, datetime

from pydantic import BaseModel


class GoalCreateRequest(BaseModel):
    title: str
    deadline: date | None = None
    priority: str | None = None


class GoalResponse(BaseModel):
    id: str
    title: str
    deadline: date | None = None
    priority: str | None = None
    status_pct: float
    created_at: datetime


class DailyPlanItem(BaseModel):
    day: int
    theme: str = ""
    tasks: list[str] = []
    deliverable: str = ""
    estimated_time: str = ""
    rationale: str = ""
    source: str = "llm"  # "llm" | "fallback"


class CareerPlanLLMOutput(BaseModel):
    """Shape the LLM itself is asked to return."""
    daily_plan: list[DailyPlanItem] = []


class SkillSignal(BaseModel):
    skill: str
    confidence: float
    is_strong: bool
    reasons: list[str] = []


class CareerPlanResponse(BaseModel):
    plan_id: str
    goal_id: str
    days_available: int
    daily_plan: list[DailyPlanItem]
    check_ins: list[str]
    generated_at: datetime
    degraded: bool = False
    skill_signals: list[SkillSignal] = []  # advisory input, shown for transparency only