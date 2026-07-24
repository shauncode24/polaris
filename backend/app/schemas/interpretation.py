from pydantic import BaseModel

from app.schemas.skill_gap import SkillGapReport


class CategoryScore(BaseModel):
    category: str
    label: str
    score: float
    skill_count: int
    matched_skills: str
    missing_skills: list[str] = []


class OverallMatch(BaseModel):
    percentage: float
    label: str
    matched_requirements: str
    required_matched: str
    nice_to_have_matched: str
    projected_percentage: float
    opportunity_narrative: str


class LearningPlanItem(BaseModel):
    skill: str
    weeks: int
    rationale: str = ""
    phase: str = ""


class NarrativeAnalysis(BaseModel):
    executive_summary: str
    role_focus: list[str] = []  # "What this company is really looking for"
    strengths: list[str] = []
    risks: list[str] = []
    hiring_perspective: str = ""
    learning_plan: list[LearningPlanItem] = []
    resume_advice: list[str] = []
    interview_focus: list[str] = []
    career_strategy: str = ""
    next_steps: list[str] = []


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