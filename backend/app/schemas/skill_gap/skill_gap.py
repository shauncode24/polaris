from typing import Literal

from pydantic import BaseModel


# How much a gap matters for this job, from how the job asks for the skill and
# how far the evidence falls short (see services/skill_gap/severity.py).
Severity = Literal["critical", "moderate", "minor"]

# Bumped when the report gains information that older stored reports lack, so
# they are rebuilt instead of served.
REPORT_VERSION = 1


class SupportingEvidence(BaseModel):
    """One concrete thing in the user's record that shows a skill."""
    kind: Literal["project", "experience", "github_repo", "leetcode_topic", "linkedin", "certificate"]
    source: str  # "resume" | "github" | "leetcode" | "linkedin" | "certificate"
    title: str  # project name, "role at company", repo name, LeetCode topic, ...
    detail: str | None = None  # the bullet or sentence that shows it, or why it counts
    item_id: str | None = None  # the project / experience in the evidence record
    url: str | None = None


class HaveSkill(BaseModel):
    skill: str
    confidence: float
    evidence: list[str]
    supporting: list[SupportingEvidence] = []
    explanation: str = ""
    # NEW — only set when a real claim-risk/timeline-plausibility
    # discount was actually applied (see
    # services/identity/confidence_reconciliation.py). Mirrors the exact
    # shape IdentityFacts.top_skills already exposes for the same reason
    # — transparency about why a confidence number reads lower than the
    # raw evidence weight alone would suggest.
    raw_confidence: float | None = None
    confidence_flags: list[str] = []


class PartialSkill(BaseModel):
    skill: str
    confidence: float
    reason: str
    severity: Severity = "moderate"
    evidence: list[str] = []
    supporting: list[SupportingEvidence] = []
    explanation: str = ""
    raw_confidence: float | None = None
    confidence_flags: list[str] = []


class MissingSkill(BaseModel):
    skill: str
    reason: str
    severity: Severity = "moderate"
    # Weak evidence that exists but is not enough to count as having the skill.
    supporting: list[SupportingEvidence] = []
    estimated_weeks: int = 0
    unmatched_explanation: str = ""


class SkillGapReport(BaseModel):
    have: list[HaveSkill] = []
    partial: list[PartialSkill] = []
    missing: list[MissingSkill] = []
    priority_order: list[str] = []
    estimated_weeks: int = 0
    evidence_version: int = 0