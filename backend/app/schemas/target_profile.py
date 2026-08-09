# backend/app/schemas/target_profile.py
from pydantic import BaseModel

from app.schemas.company_intelligence import CompanyIntelligenceProfile
from app.schemas.job_intelligence import JobIntelligenceProfile


class TargetProfile(BaseModel):
    """Composition of Job Intelligence + Company Intelligence — 'the
    complete engineer required for this opportunity' (revision,
    "Introduce a Target Profile Layer"). Never persisted on its own;
    always assembled fresh from its two already-built source profiles,
    so future Target Profile inputs (recruiter notes, interview
    experiences, etc.) only ever require a change in
    target_profile/builder.py, never in the Comparison Engine.
    """
    job_intelligence: JobIntelligenceProfile
    company_intelligence: CompanyIntelligenceProfile | None = None