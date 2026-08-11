# backend/app/services/target_profile/builder.py
from app.schemas.job_intelligence.company_intelligence import CompanyIntelligenceProfile
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.schemas.job_intelligence.target_profile import TargetProfile


def build_target_profile(
    job_intelligence: JobIntelligenceProfile,
    company_intelligence: CompanyIntelligenceProfile | None = None,
) -> TargetProfile:
    """Pure composition — no DB access. Job Intelligence and Company
    Intelligence are already-built profiles by the time this is called.
    The Comparison Engine and every downstream module should depend on
    TargetProfile, never directly on JobIntelligenceProfile, so future
    Target Profile inputs only ever require a change here.
    """
    return TargetProfile(job_intelligence=job_intelligence, company_intelligence=company_intelligence)