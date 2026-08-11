from pydantic import BaseModel

from app.schemas.role_fit import RoleFitResult


class FlagshipProject(BaseModel):
    name: str
    reason: str


class SkillConfidenceExplanation(BaseModel):
    skill: str
    explanation: str


class EngineeringHabit(BaseModel):
    observation: str
    is_strength: bool


class RecruiterPerspective(BaseModel):
    notices: list[str] = []
    decision: str = ""


class GithubPortfolioReviewLLMOutput(BaseModel):
    """Shape the LLM is asked to return — interpretation only. It never
    decides what technologies/scores exist; those are given as fact in
    the github_knowledge object it's handed (same boundary as
    resume/reviewer.py's LLMReviewOutput).

    `role_fit` is NOT populated by this call anymore — it's overwritten
    after the fact by the single shared, entirely-LLM-generated
    services/identity/role_fit.get_role_fit(scope="github_only") (fix #2).
    The field stays here only so the response shape is unchanged.
    """

    engineering_assessment: str = ""
    flagship_projects: list[FlagshipProject] = []
    role_fit: list[RoleFitResult] = []
    skill_confidence_explanations: list[SkillConfidenceExplanation] = []
    engineering_habits: list[EngineeringHabit] = []
    recruiter_perspective: RecruiterPerspective = RecruiterPerspective()
    resume_integration_suggestions: list[str] = []
    growth_story: str = ""
    improvement_roadmap: list[str] = []


class GithubPortfolioReviewReport(GithubPortfolioReviewLLMOutput):
    generated_at: str = ""
    analysis_degraded: bool = False