# backend/app/schemas/job_intelligence.py
from pydantic import BaseModel

from app.schemas.company_intelligence import ExtractedCompanySignals


class RoleIdentity(BaseModel):
    """Audit points #8-11: title/designation/grade are distinct concepts
    that were previously flattened into a single "role" string. Grade
    ("Senior Executive") is explicitly NOT the same thing as engineering
    seniority ("Senior") — conflating them was part of the seniority bug.
    """
    title: str | None = None
    designation: str | None = None
    grade: str | None = None
    function: str | None = None
    department: str | None = None
    location: str | None = None
    reports_to: str | None = None
    employment_type: str | None = None


class EligibilityRequirement(BaseModel):
    """e.g. {"requirement": "CGPA", "detail": "8+"} or
    {"requirement": "Education", "detail": "BTech/MTech in Computer Science"}.
    Kept as free-text detail rather than a strict numeric field — JDs
    phrase eligibility bars too inconsistently for a single numeric type
    to hold them all without silently dropping real ones.
    """
    requirement: str
    detail: str = ""


class QualificationRequirements(BaseModel):
    """Audit point #4 — hard eligibility bars, structurally distinct
    from "skills". A candidate can have every required skill and still
    be ineligible on education/CGPA — that's a different kind of fact
    and deserves its own field, not a blended requirements list.
    """
    education: list[str] = []
    eligibility: list[EligibilityRequirement] = []
    experience: str | None = None


class ExtractedSkillRequirement(BaseModel):
    """Audit point #7 — a skill plus the JD's own proficiency language
    for it ("good knowledge of" vs "exposure to" vs "familiarity with").
    Only required_skills and nice_to_have carry this — implicit_skills
    are the model's own inference, not a literal quoted phrase, so they
    have no proficiency language to extract in the first place.
    """
    skill: str
    proficiency_signal: str = "not_specified"  # "good_knowledge" | "hands_on" | "exposure" | "familiarity" | "not_specified"


class ExtractedJobRequirements(BaseModel):
    """Role-side half of the combined extraction call."""
    required_skills: list[ExtractedSkillRequirement] = []
    implicit_skills: list[str] = []
    architecture_topics: list[str] = []
    capabilities: list[str] = []
    nice_to_have: list[ExtractedSkillRequirement] = []
    responsibilities: list[str] = []
    role_identity: RoleIdentity = RoleIdentity()
    job_purpose: str | None = None
    qualification_requirements: QualificationRequirements = QualificationRequirements()
    company: str | None = None
    role: str | None = None


class ExtractedJobAndCompany(BaseModel):
    """The raw shape of the ONE LLM extraction call — see
    prompts/job_intelligence.py."""
    job: ExtractedJobRequirements
    company: ExtractedCompanySignals = ExtractedCompanySignals()


class EnrichedSkill(BaseModel):
    raw: str
    canonical: str
    category: str
    curriculum_phase: str
    requirement_type: str  # "required" | "implicit" | "nice_to_have"
    proficiency_signal: str = "not_specified"


class SeniorityLevel(BaseModel):
    level: str = "unspecified"  # "intern" | "junior" | "mid" | "senior" | "staff" | "unspecified"
    evidence: list[str] = []
    confidence: str = "low"  # "low" | "medium" | "high"


class ExtractionQuality(BaseModel):
    score: float = 0.0
    label: str = "Low"
    reasons: list[str] = []


class InterviewFocusAreas(BaseModel):
    """Audit point #15 — explicit (literally required skills/architecture
    topics) vs inferred (seniority-driven additions like "system design
    & trade-off reasoning" that the JD never states outright). Keeping
    these separate means a consumer never has to guess which tier a
    given focus area came from.
    """
    explicit: list[str] = []
    inferred: list[str] = []


class JobIntelligenceProfile(BaseModel):
    """The Job Intelligence analogue of IdentityFacts — a user-independent
    representation of what a role requires. Never reads anything about a
    specific candidate.

    "capabilities" is now a REAL, independently-extracted field (action-
    oriented — "what will you actually do") — it previously duplicated
    architecture_topics verbatim and was removed; this reintroduces it
    with its own extraction question so the two fields carry genuinely
    different information (audit point #2).
    """
    id: str | None = None
    role: str | None = None
    company: str | None = None
    role_identity: RoleIdentity = RoleIdentity()
    job_purpose: str = ""
    responsibilities: list[str] = []
    enriched_required_skills: list[EnrichedSkill] = []
    enriched_implicit_skills: list[EnrichedSkill] = []
    enriched_nice_to_have: list[EnrichedSkill] = []
    capabilities: list[str] = []
    architecture_topics: list[str] = []
    qualification_requirements: QualificationRequirements = QualificationRequirements()
    seniority_signal: SeniorityLevel = SeniorityLevel()
    resume_keywords: list[str] = []
    # Kept flat for backward compatibility — career_planner/context_builder.py
    # and interview/context_builder.py already read this field directly.
    interview_focus_areas: list[str] = []
    # NEW — the same information, split by provenance (audit #15).
    interview_focus: InterviewFocusAreas = InterviewFocusAreas()
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
        out: dict[str, str] = {}
        for group, rtype in (
            (self.enriched_required_skills, "required"),
            (self.enriched_implicit_skills, "implicit"),
            (self.enriched_nice_to_have, "nice_to_have"),
        ):
            for s in group:
                out.setdefault(s.canonical, rtype)
        return out


class JobIntelligenceSummary(BaseModel):
    id: str
    role: str | None = None
    company: str | None = None
    seniority_level: str = "unspecified"
    extraction_quality_label: str = "Low"
    created_at: str | None = None