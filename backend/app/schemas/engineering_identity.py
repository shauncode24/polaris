from datetime import datetime

from pydantic import BaseModel


class IdentityFacts(BaseModel):
    """Deterministic facts pulled from every module — the ONLY thing the
    synthesis LLM call (identity_synthesizer.py) is allowed to reason
    over. Nothing in this object is LLM-generated.
    """
    top_skills: list[dict] = []                    # {"skill","confidence","sources":[...]}
    role_fit: list[dict] = []                       # from role_fit.compute_combined_role_fit
    resume_score: float | None = None
    resume_grade: str | None = None
    github_summary: dict = {}
    github_progress: dict = {}
    architecture_maturity: dict = {}
    technology_depth_highlights: list[dict] = []     # top N by depth score
    leetcode_summary: dict = {}
    leetcode_topic_mastery: list[dict] = []
    coverage_gaps: dict = {}
    timeline_plausibility_notes: list[dict] = []
    active_goals: list[dict] = []
    recent_job_matches: list[dict] = []
    claim_risk_summary: dict = {}


class IdentityLLMOutput(BaseModel):
    headline: str = ""
    summary: str = ""
    strongest_signals: list[str] = []
    biggest_gaps: list[str] = []
    contradictions: list[str] = []
    recommended_focus: str = ""


class EngineeringIdentityReport(BaseModel):
    facts: IdentityFacts
    narrative: IdentityLLMOutput
    generated_at: datetime | None = None
    analysis_degraded: bool = False