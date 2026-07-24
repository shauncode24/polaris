from pydantic import BaseModel


class ExtractedJDRequirements(BaseModel):
    required_skills: list[str] = []
    implicit_skills: list[str] = []
    architecture_topics: list[str] = []
    nice_to_have: list[str] = []
    company: str | None = None
    role: str | None = None


class JDPasteRequest(BaseModel):
    raw_text: str
    company: str | None = None
    role: str | None = None


class HaveSkill(BaseModel):
    skill: str
    confidence: float
    evidence: list[str]
    explanation: str = ""


class PartialSkill(BaseModel):
    skill: str
    confidence: float
    reason: str
    explanation: str = ""


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