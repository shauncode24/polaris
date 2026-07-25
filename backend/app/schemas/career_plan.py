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
    day_type: str = ""
    tasks: list[str] = []
    deliverable: str = ""
    estimated_time: str = ""
    rationale: str = ""
    source: str = "llm"  # "llm" | "fallback"


class CareerPlanLLMOutput(BaseModel):
    daily_plan: list[DailyPlanItem] = []


class TopicSignal(BaseModel):
    domain: str
    topic: str
    suggested_order: int
    coverage: str
    confidence: float | None = None
    reasons: list[str] = []


class CareerPlanResponse(BaseModel):
    plan_id: str
    goal_id: str
    days_available: int
    relevant_domains: list[str] = []
    daily_plan: list[DailyPlanItem]
    check_ins: list[str]
    generated_at: datetime
    degraded: bool = False
    topic_signals: list[TopicSignal] = []