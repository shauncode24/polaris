# backend/app/schemas/company_intelligence.py
from pydantic import BaseModel


class CompanySignals(BaseModel):
    """Structured company-culture categories (audit point #14) — replaces
    the old flat "culture_hints" bucket so a consumer doesn't have to
    guess what kind of hint each string is. Every category defaults to
    empty; a category with nothing genuinely stated in the JD stays
    empty rather than being padded.
    """
    culture: list[str] = []
    values: list[str] = []
    work_environment: list[str] = []
    learning_development: list[str] = []
    diversity_inclusion: list[str] = []
    recognition: list[str] = []


class ExtractedCompanySignals(BaseModel):
    """Company-side half of the single combined extraction call. Only
    what is literally extractable from the job description text itself
    — never inferred (design doc revision, "Company Intelligence During
    Phase 1").
    """
    industry: str | None = None
    # NEW (review finding #11) — the company's real business domain(s)
    # as stated/clearly implied in the text (e.g. "Retail Financial
    # Services", "Lending", "Wealth Management"), distinct from
    # "industry" (one short phrase) and from "products_mentioned" (named
    # products). Empty list if the text gives nothing beyond industry.
    domain: list[str] = []
    products_mentioned: list[str] = []
    technologies_mentioned: list[str] = []
    engineering_hints: list[str] = []
    company_signals: CompanySignals = CompanySignals()


class CompanyIntelligenceProfile(BaseModel):
    """Persisted Company Intelligence — 'how does this company hire and
    operate', independent of any specific role or candidate.
    """
    id: str | None = None
    company: str | None = None
    industry: str | None = None
    domain: list[str] = []
    products_mentioned: list[str] = []
    technologies_mentioned: list[str] = []
    engineering_hints: list[str] = []
    company_signals: CompanySignals = CompanySignals()
    source_text_hash: str = ""
    created_at: str | None = None