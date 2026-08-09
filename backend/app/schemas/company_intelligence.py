# backend/app/schemas/company_intelligence.py
from pydantic import BaseModel


class ExtractedCompanySignals(BaseModel):
    """Company-side half of the single combined extraction call (design
    doc revision, "One Input, One LLM Call"). Deliberately shallow —
    Company Intelligence in Phase 1 only contains what's literally
    extractable from the job description text itself; it never infers
    company info that isn't there (revision, "Company Intelligence
    During Phase 1").
    """
    industry: str | None = None
    products_mentioned: list[str] = []
    technologies_mentioned: list[str] = []
    engineering_hints: list[str] = []
    culture_hints: list[str] = []


class CompanyIntelligenceProfile(BaseModel):
    """Persisted Company Intelligence — 'how does this company hire and
    operate', independent of any specific role or candidate. Kept as a
    fully separate module from Job Intelligence even though both are
    produced from the same job description text right now (revision,
    "Company Intelligence Should Remain Independent") — one company can
    post many roles, and this profile is meant to later be enriched from
    other sources (recruiter notes, interview experiences) without ever
    touching Job Intelligence's pipeline.
    """
    id: str | None = None
    company: str | None = None
    industry: str | None = None
    products_mentioned: list[str] = []
    technologies_mentioned: list[str] = []
    engineering_hints: list[str] = []
    culture_hints: list[str] = []
    source_text_hash: str = ""
    created_at: str | None = None