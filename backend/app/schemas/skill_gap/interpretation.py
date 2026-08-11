# backend/app/schemas/interpretation.py
from pydantic import BaseModel

from app.schemas.skill_gap.skill_gap import SkillGapReport


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


class NarrativeAnalysis(BaseModel):
    """Diagnostic narrative only — no career planning, resume advice,
    hiring-manager roleplay, or interview prep. Those belong to other
    modules (Career Planner, Interview). This model answers strictly:
    how well does this profile match this role, where are the strengths,
    and where are the gaps?
    """
    executive_summary: str
    role_focus: list[str] = []
    strengths: list[str] = []
    risks: list[str] = []


class SkillGapAnalysisResponse(BaseModel):
    """The Comparison Engine's output — user-vs-role comparison only.
    Deliberately owns nothing from Job Intelligence or Company
    Intelligence beyond what analyze_skill_gap/narrative.py already
    compute (role_focus is grounded in job_intelligence.interview_focus_areas
    but never re-exposing the raw role/company facts here — those live
    exclusively in the separate Job Intelligence module/page).
    """
    report: SkillGapReport
    category_breakdown: list[CategoryScore] = []
    overall_match: OverallMatch
    analysis: NarrativeAnalysis
    analysis_degraded: bool = False