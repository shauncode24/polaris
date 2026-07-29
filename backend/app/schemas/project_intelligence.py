from pydantic import BaseModel


class ProjectIntelligenceLLMOutput(BaseModel):
    synthesis: str = ""
    framing_response: str = ""
    strengths: list[str] = []
    gaps: list[str] = []
    talking_points: list[str] = []
    insufficient_context: bool = False
    context_note: str = ""


class ProjectComparisonLLMOutput(BaseModel):
    comparison_summary: str = ""
    this_project_strengths: list[str] = []
    comparison_target_strengths: list[str] = []
    recommendation: str = ""
    insufficient_context: bool = False
    context_note: str = ""


class ProjectIntelligenceReport(ProjectIntelligenceLLMOutput):
    project_id: str
    framing: str
    generated_at: str = ""


class ProjectComparisonReport(ProjectComparisonLLMOutput):
    project_id: str
    comparison_target: str
    generated_at: str = ""