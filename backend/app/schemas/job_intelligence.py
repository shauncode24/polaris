# backend/app/schemas/job_intelligence.py
from pydantic import BaseModel

from app.schemas.company_intelligence import ExtractedCompanySignals


class ExtractedJobRequirements(BaseModel):
    """Role-side half of the combined extraction call. Same shape as the
    legacy ExtractedJDRequirements (app/schemas/skill_gap.py) — kept as
    a distinct class under job_intelligence per the design doc's package
    split, rather than reusing the old one, so Job Intelligence never
    depends on the legacy jobs/ package.
    """
    required_skills: list[str] = []
    implicit_skills: list[str] = []
    architecture_topics: list[str] = []
    nice_to_have: list[str] = []
    company: str | None = None
    role: str | None = None


class ExtractedJobAndCompany(BaseModel):
    """The raw shape of the ONE LLM extraction call — see
    prompts/job_intelligence.py. The backend splits this into two
    independent profiles immediately after parsing (revision, "One
    Input, One LLM Call")."""
    job: ExtractedJobRequirements
    company: ExtractedCompanySignals = ExtractedCompanySignals()


class EnrichedSkill(BaseModel):
    raw: str
    canonical: str
    category: str
    curriculum_phase: str
    requirement_type: str  # "required" | "implicit" | "nice_to_have"


class SeniorityLevel(BaseModel):
    level: str = "unspecified"  # "intern" | "junior" | "mid" | "senior" | "staff" | "unspecified"
    evidence: list[str] = []
    confidence: str = "low"  # "low" | "medium" | "high"


class ExtractionQuality(BaseModel):
    score: float = 0.0
    label: str = "Low"
    reasons: list[str] = []


class JobIntelligenceProfile(BaseModel):
    """The Job Intelligence analogue of IdentityFacts — a user-independent
    representation of what a role requires. Never reads anything about a
    specific candidate (design doc §2.1)."""
    id: str | None = None
    role: str | None = None
    company: str | None = None
    enriched_required_skills: list[EnrichedSkill] = []
    enriched_implicit_skills: list[EnrichedSkill] = []
    enriched_nice_to_have: list[EnrichedSkill] = []
    architecture_topics: list[str] = []
    capabilities: list[str] = []
    seniority_signal: SeniorityLevel = SeniorityLevel()
    resume_keywords: list[str] = []
    interview_focus_areas: list[str] = []
    extraction_quality: ExtractionQuality = ExtractionQuality()
    source_text_hash: str = ""
    created_at: str | None = None

    @property
    def all_required_technologies(self) -> list[str]:
        return sorted({
            s.canonical for s in self.enriched_required_skills + self.enriched_implicit_skills
        })

    @property
    def canonical_skills_map(self) -> dict[str, str]:
        """canonical -> requirement_type, precedence required > implicit
        > nice_to_have — the exact precedence rule api/jobs.py used
        before this refactor, now owned here instead of re-derived by
        every caller.
        """
        out: dict[str, str] = {}
        for group, rtype in (
            (self.enriched_required_skills, "required"),
            (self.enriched_implicit_skills, "implicit"),
            (self.enriched_nice_to_have, "nice_to_have"),
        ):
            for s in group:
                out.setdefault(s.canonical, rtype)
        return out