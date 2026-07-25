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


class WeeklyPlanItem(BaseModel):
    week: int
    focus: list[str] = []
    rationale: str = ""


class CareerPlanLLMOutput(BaseModel):
    """Shape the LLM itself is asked to return — nothing else."""
    weekly_plan: list[WeeklyPlanItem] = []
    milestone_check_ins: list[str] = []


class CareerPlanResponse(BaseModel):
    plan_id: str
    goal_id: str
    weeks_available: int
    weekly_plan: list[WeeklyPlanItem]
    milestone_check_ins: list[str]
    generated_at: datetime
    degraded: bool = False