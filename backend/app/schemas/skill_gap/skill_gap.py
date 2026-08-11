from pydantic import BaseModel


class JDPasteRequest(BaseModel):
    raw_text: str
    company: str | None = None
    role: str | None = None


class HaveSkill(BaseModel):
    skill: str
    confidence: float
    evidence: list[str]
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
    explanation: str = ""
    raw_confidence: float | None = None
    confidence_flags: list[str] = []


class MissingSkill(BaseModel):
    skill: str
    reason: str
    estimated_weeks: int = 0
    unmatched_explanation: str = ""


class SkillGapReport(BaseModel):
    have: list[HaveSkill] = []
    partial: list[PartialSkill] = []
    missing: list[MissingSkill] = []
    priority_order: list[str] = []
    estimated_weeks: int = 0