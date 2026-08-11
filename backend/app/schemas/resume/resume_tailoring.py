from pydantic import BaseModel


class RankedItem(BaseModel):
    id: str
    type: str  # "project" | "experience"
    label: str
    relevance_score: float
    matched_skills: list[str] = []


class TailoringLLMOutput(BaseModel):
    lead_items: list[str] = []          # ids, validated against ranked_items
    cut_bullets: list[str] = []         # bullet_ids, validated
    emphasize_bullets: list[str] = []   # bullet_ids, validated
    rationale: str = ""


class TailoringReport(BaseModel):
    role: str | None = None
    company: str | None = None
    ranked_items: list[RankedItem] = []
    llm: TailoringLLMOutput
    analysis_degraded: bool = False