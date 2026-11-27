"""Every model of the comparison between a user's evidence and one job: what
the comparison engine produces, what is stored, and what the Skill Gap page
and the job library receive.
"""
from typing import Literal

from pydantic import BaseModel

from app.schemas.job_intelligence.company_intelligence import CompanyIntelligenceProfile
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile


# How much a gap matters for this job, from how the job asks for the skill and
# how far the evidence falls short (see services/skill_gap/severity.py).
Severity = Literal["critical", "moderate", "minor"]

# Bumped when the report changes in a way older stored reports can't satisfy,
# so they are rebuilt instead of served.
REPORT_VERSION = 2


class SupportingEvidence(BaseModel):
    """One concrete thing in the user's record that shows a skill."""
    kind: Literal["project", "experience", "github_repo", "leetcode_topic", "linkedin", "certificate"]
    source: str  # "resume" | "github" | "leetcode" | "linkedin" | "certificate"
    title: str  # project name, "role at company", repo name, LeetCode topic, ...
    detail: str | None = None  # the bullet or sentence that shows it, or why it counts
    item_id: str | None = None  # the project / experience in the evidence record
    url: str | None = None


# --- one requirement --------------------------------------------------------

class SkillMatch(BaseModel):
    """What the comparison says about one of the job's requirements."""
    skill: str
    explanation: str = ""
    # What the user's record shows for it. For a gap this is weak evidence
    # that exists but is not enough to count.
    supporting: list[SupportingEvidence] = []


class EvidencedSkill(SkillMatch):
    """A requirement the user has some countable evidence for."""
    confidence: float
    # Only set when a real claim-risk or timeline discount was applied, so the
    # page can say why the number reads lower than the evidence alone would.
    raw_confidence: float | None = None
    confidence_flags: list[str] = []


class HaveSkill(EvidencedSkill):
    pass


class PartialSkill(EvidencedSkill):
    reason: str
    severity: Severity = "moderate"


class MissingSkill(SkillMatch):
    reason: str
    severity: Severity = "moderate"
    estimated_weeks: int = 0


# --- one job ----------------------------------------------------------------

class SkillGapReport(BaseModel):
    have: list[HaveSkill] = []
    partial: list[PartialSkill] = []
    missing: list[MissingSkill] = []
    priority_order: list[str] = []
    estimated_weeks: int = 0
    evidence_version: int = 0


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


class SkillGapForJobResponse(BaseModel):
    """The Skill Gap page's single response: the parsed job the user picked
    and the whole comparison, so the page needs no second request.
    """
    job_intelligence: JobIntelligenceProfile
    company_intelligence: CompanyIntelligenceProfile | None = None
    report: SkillGapReport
    category_breakdown: list[CategoryScore] = []
    overall_match: OverallMatch
    analysis: NarrativeAnalysis
    analysis_degraded: bool = False
    generated_at: str
