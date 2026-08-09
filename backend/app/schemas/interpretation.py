# backend/app/schemas/interpretation.py — back to original, no Job/Company Intelligence fields
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
    role_focus: list[str] = []
    strengths: list[str] = []
    risks: list[str] = []
    hiring_perspective: str = ""
    learning_plan: list[LearningPlanItem] = []
    resume_advice: list[str] = []
    interview_focus: list[str] = []
    career_strategy: str = ""
    next_steps: list[str] = []


class SkillGapAnalysisResponse(BaseModel):
    """The Comparison Engine's output — user-vs-role comparison only.
    Deliberately owns nothing from Job Intelligence or Company
    Intelligence beyond what analyze_skill_gap/narrative.py already
    compute (role_focus/interview_focus are personalized narrative
    fields, grounded internally in job_intelligence.interview_focus_areas
    but never re-exposing the raw role/company facts here — those live
    exclusively in the separate Job Intelligence module/page).
    """
    report: SkillGapReport
    category_breakdown: list[CategoryScore] = []
    overall_match: OverallMatch
    analysis: NarrativeAnalysis
    analysis_degraded: bool = False