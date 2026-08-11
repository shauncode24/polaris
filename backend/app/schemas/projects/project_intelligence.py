# from pydantic import BaseModel


# class ProjectIntelligenceLLMOutput(BaseModel):
#     synthesis: str = ""
#     framing_response: str = ""
#     strengths: list[str] = []
#     gaps: list[str] = []
#     talking_points: list[str] = []
#     insufficient_context: bool = False
#     context_note: str = ""


# class ProjectComparisonLLMOutput(BaseModel):
#     comparison_summary: str = ""
#     this_project_strengths: list[str] = []
#     comparison_target_strengths: list[str] = []
#     recommendation: str = ""
#     insufficient_context: bool = False
#     context_note: str = ""


# class ProjectIntelligenceReport(ProjectIntelligenceLLMOutput):
#     project_id: str
#     framing: str
#     generated_at: str = ""


# class ProjectComparisonReport(ProjectComparisonLLMOutput):
#     project_id: str
#     comparison_target: str
#     generated_at: str = ""

from pydantic import BaseModel


class ClaimAuditFacts(BaseModel):
    project_name: str
    has_repo_match: bool
    unsupported_claims: list[str] = []
    undersold_work: list[str] = []
    confirmed_claims: list[str] = []
    architecture_flag: str | None = None
    risk_level: str = "low"
    verified_facts: dict = {}


class ClaimAuditNarrative(BaseModel):
    headline: str = ""
    risk_level: str = "low"  # "low" | "medium" | "high"
    talking_points: list[str] = []
    fixes: list[str] = []


class ClaimAuditReport(BaseModel):
    facts: ClaimAuditFacts
    narrative: ClaimAuditNarrative
    analysis_degraded: bool = False


class ProjectIntelligenceLLMOutput(BaseModel):
    framing: str = ""
    explanation: str = ""
    strongest_technical_decision: str = ""
    weakest_point: str = ""
    comparison_target: str | None = None
    comparison_notes: str = ""
    insufficient_context: bool = False
    context_note: str = ""


class ProjectIntelligenceReport(ProjectIntelligenceLLMOutput):
    project_name: str = ""
    generated_at: str = ""
    analysis_degraded: bool = False


class InterviewQuestionItem(BaseModel):
    question: str
    grounded_in: str = ""
    difficulty: str = "medium"  # "easy" | "medium" | "hard"


class InterviewQuestionsLLMOutput(BaseModel):
    questions: list[InterviewQuestionItem] = []


class InterviewQuestionsReport(BaseModel):
    project_name: str
    questions: list[InterviewQuestionItem] = []
    generated_at: str = ""
    analysis_degraded: bool = False


class PortfolioNarrativeLLMOutput(BaseModel):
    eligible: bool = True
    narrative: str = ""
    testing_pattern: str = ""
    collaboration_pattern: str = ""
    specialization: str = ""
    biggest_weakness: str = ""


class PortfolioNarrativeReport(PortfolioNarrativeLLMOutput):
    generated_at: str = ""
    analysis_degraded: bool = False


class GoalAwareRanking(BaseModel):
    project_id: str
    project_name: str
    score: float
    reasons: list[str] = []


class PortfolioComparisonResponse(BaseModel):
    ranked: list[GoalAwareRanking] = []
    lead_project: str | None = None
    recommendation: str = ""