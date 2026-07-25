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
    focus: list[str] = []
    rationale: str = ""
    source: str = "llm"  # "llm" | "fallback" — lets the UI distinguish
                          # model-reasoned days from the deterministic
                          # safety-net text used only when the LLM call
                          # genuinely fails, not as the default path.


class CareerPlanLLMOutput(BaseModel):
    """Shape the LLM itself is asked to return — nothing else."""
    daily_plan: list[DailyPlanItem] = []
    check_ins: list[str] = []


class CareerPlanResponse(BaseModel):
    plan_id: str
    goal_id: str
    days_available: int
    daily_plan: list[DailyPlanItem]
    check_ins: list[str]
    generated_at: datetime
    degraded: bool = False