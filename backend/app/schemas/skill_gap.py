from pydantic import BaseModel


class ExtractedJDRequirements(BaseModel):
    required_skills: list[str] = []
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


class MissingSkill(BaseModel):
    skill: str
    reason: str


class SkillGapReport(BaseModel):
    have: list[HaveSkill] = []
    missing: list[MissingSkill] = []
    priority_order: list[str] = []
    estimated_weeks: int = 0