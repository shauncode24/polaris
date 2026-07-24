from pydantic import BaseModel

from app.schemas.skill_gap import SkillGapReport


class CategoryScore(BaseModel):
    category: str
    label: str
    score: float
    skill_count: int


class OverallMatch(BaseModel):
    percentage: float
    label: str


class LearningPlanItem(BaseModel):
    skill: str
    weeks: int
    rationale: str


class NarrativeAnalysis(BaseModel):
    executive_summary: str
    strengths: list[str] = []
    risks: list[str] = []
    learning_plan: list[LearningPlanItem] = []
    resume_advice: list[str] = []
    interview_focus: list[str] = []
    confidence_narrative: str = ""


class SkillGapAnalysisResponse(BaseModel):
    """What the API actually returns now. `report` is the deterministic
    machine output (unchanged, still safe for any future non-LLM consumer
    like Career Planner); `analysis` is what actually renders as prose in
    the UI.
    """
    report: SkillGapReport
    category_breakdown: list[CategoryScore] = []
    overall_match: OverallMatch
    analysis: NarrativeAnalysis
    analysis_degraded: bool = False