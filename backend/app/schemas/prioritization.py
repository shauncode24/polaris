from pydantic import BaseModel


class PrioritizationResult(BaseModel):
    priority_order: list[str] = []
    estimated_weeks: dict[str, int] = {}