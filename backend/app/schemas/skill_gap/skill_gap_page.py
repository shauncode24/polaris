# backend/app/schemas/skill_gap_page.py
"""Response shape for the Skill Gap page's single entry point: an
already-parsed JobIntelligenceProfile (selected by the user) plus the
full comparison against the candidate's Engineering Identity. Bundles
the job's own facts (role_identity, enriched skills, canonical_skills_map
for required/implicit/nice_to_have lookups) alongside the comparison
result so the frontend never has to make a second round trip or
recompute a requirement-type mapping itself.
"""
from pydantic import BaseModel

from app.schemas.job_intelligence.company_intelligence import CompanyIntelligenceProfile
from app.schemas.skill_gap.interpretation import CategoryScore, NarrativeAnalysis, OverallMatch
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.schemas.skill_gap.skill_gap import SkillGapReport


class SkillGapForJobResponse(BaseModel):
    job_intelligence: JobIntelligenceProfile
    company_intelligence: CompanyIntelligenceProfile | None = None
    report: SkillGapReport
    category_breakdown: list[CategoryScore] = []
    overall_match: OverallMatch
    analysis: NarrativeAnalysis
    analysis_degraded: bool = False
    generated_at: str