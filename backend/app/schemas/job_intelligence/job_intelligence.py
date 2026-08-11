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


class ExperienceRequirement(BaseModel):
    """Review finding #1 — `experience` used to be `str | None`, which
    collapsed to null whenever a JD didn't state a bare "N years"
    figure. That silently dropped requirements phrased as "hands-on
    experience through internships/projects" — a real, structured
    experience bar that just isn't a year count. `minimum_years` staying
    null does NOT mean there is no experience requirement; that's why
    this is its own object instead of falling back to `str | None`.
    """
    raw: str | None = None
    experience_type: str = "not_specified"  # "internship_or_project" | "professional" | "not_specified"
    domain: str | None = None               # e.g. "full_stack_development"
    minimum_years: float | None = None
    proficiency_signal: str = "not_specified"


class QualificationRequirements(BaseModel):
    """Audit point #4 — hard eligibility bars, structurally distinct
    from "skills". A candidate can have every required skill and still
    be ineligible on education/CGPA — that's a different kind of fact
    and deserves its own field, not a blended requirements list.
    """
    education: list[str] = []
    eligibility: list[EligibilityRequirement] = []
    experience: ExperienceRequirement | None = None


class ExtractedSkillRequirement(BaseModel):
    """Audit point #7 — a skill plus the JD's own proficiency language
    for it ("good knowledge of" vs "exposure to" vs "familiarity with").
    Used for required_skills and nice_to_have, which both carry literal
    quoted JD proficiency language.
    """
    skill: str
    proficiency_signal: str = "not_specified"  # "good_knowledge" | "hands_on" | "exposure" | "familiarity" | "not_specified"


class ExtractedImplicitSkill(BaseModel):
    """Review finding #5 — implicit_skills used to be plain strings,
    which let a model's own inference (e.g. "REST API Design") reach the
    UI looking exactly as authoritative as a literally-stated
    requirement. Every implicit skill now carries the real
    responsibility/phrase it was inferred from ("evidence") and a
    confidence level, so downstream consumers (and the UI) can visually
    distinguish "the JD said this" from "the model inferred this."
    """
    skill: str
    evidence: str = ""
    confidence: str = "medium"  # "low" | "medium" | "high"


class ExtractedJobRequirements(BaseModel):
    """Role-side half of the combined extraction call."""
    required_skills: list[ExtractedSkillRequirement] = []
    implicit_skills: list[ExtractedImplicitSkill] = []
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
    # Only meaningful for requirement_type == "implicit" (see
    # ExtractedImplicitSkill above). Left at their defaults for
    # required/nice_to_have entries, where the skill was a literal JD
    # quote rather than a model inference — "confidence" defaulting to
    # "high" there reflects that it's a direct citation, not a guess.
    evidence: str = ""
    confidence: str = "high"


class SeniorityLevel(BaseModel):
    level: str = "unspecified"  # "intern" | "junior" | "mid" | "senior" | "staff" | "unspecified"
    evidence: list[str] = []
    confidence: str = "low"  # "low" | "medium" | "high"


class ExtractionQuality(BaseModel):
    score: float = 0.0             # overall 0-1 composite
    job_completeness: float = 0.0  # fraction of job fields populated
    company_completeness: float = 0.0  # fraction of company fields populated
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


class ResumeKeywordTiers(BaseModel):
    """Review finding #8 — a single flat, deduplicated keyword list
    conflates three genuinely different things: the JD's own literal
    phrasing ("raw"), Polaris' internal normalized/canonical form
    ("canonical"), and the subset that's actually worth putting ON a
    resume ("resume_relevant" — skill/architecture terms, never
    role-identity or company boilerplate). `resume_keywords` on
    JobIntelligenceProfile is left completely unchanged (still a flat
    list) so any existing caller keeps working untouched; this is an
    additive, richer companion view for the UI.
    """
    raw: list[str] = []
    canonical: list[str] = []
    resume_relevant: list[str] = []


class JobIntelligenceProfile(BaseModel):
    """The Job Intelligence analogue of IdentityFacts — a user-independent
    representation of what a role requires. Never reads anything about a
    specific candidate.
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
    # UNCHANGED shape (flat list) — kept for backward compatibility with
    # any existing caller. See resume_keyword_tiers for the richer view.
    resume_keywords: list[str] = []
    resume_keyword_tiers: ResumeKeywordTiers = ResumeKeywordTiers()
    interview_focus_areas: list[str] = []
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