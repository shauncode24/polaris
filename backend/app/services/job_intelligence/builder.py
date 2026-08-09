# backend/app/services/job_intelligence/builder.py
"""Stages 9-11 — assembles and persists the complete JobIntelligenceProfile
+ CompanyIntelligenceProfile from ONE extraction call. build_job_intelligence()
is the single function every other module should call or read the
persisted result of — never re-implement extraction (design doc §2.7).
"""
import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_intelligence import CompanyIntelligenceProfileRow, JobIntelligenceProfileRow
from app.schemas.company_intelligence import CompanyIntelligenceProfile
from app.schemas.job_intelligence import ExtractionQuality, JobIntelligenceProfile
from app.services.job_intelligence.extraction import JobIntelligenceExtractionError, extract_job_and_company
from app.services.job_intelligence.interview_focus import derive_interview_focus_areas
from app.services.job_intelligence.keywords import derive_resume_keywords
from app.services.job_intelligence.normalization import enrich_skills
from app.services.job_intelligence.seniority import detect_seniority_with_fallback

__all__ = ["build_job_intelligence", "get_job_intelligence", "JobIntelligenceExtractionError"]


def _source_text_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.strip().encode()).hexdigest()


def _compute_extraction_quality(raw_text: str, total_requirements: int) -> ExtractionQuality:
    """Stage 9 — self-assessed extraction confidence, so downstream
    consumers (and the UI) never present a sparse profile as if it were
    authoritative (design doc §2.3, "confidence / extraction_quality").
    """
    word_count = len(raw_text.split())
    reasons: list[str] = []
    score = 1.0
    if word_count < 80:
        score -= 0.4
        reasons.append(f"Job description is short (~{word_count} words)")
    if total_requirements < 3:
        score -= 0.3
        reasons.append(f"Only {total_requirements} requirement(s) were extracted")
    score = max(0.0, min(1.0, score))
    if not reasons:
        reasons.append("Job description had enough detail to extract confidently")
    label = "High" if score >= 0.75 else ("Medium" if score >= 0.4 else "Low")
    return ExtractionQuality(score=round(score, 2), label=label, reasons=reasons)


async def build_job_intelligence(
    db: AsyncSession, user_id, raw_text: str, company: str | None = None, role: str | None = None,
) -> tuple[JobIntelligenceProfile, CompanyIntelligenceProfile]:
    """Raises JobIntelligenceExtractionError if the combined extraction
    call fails or returns something unvalidatable — callers (api/jobs.py,
    api/job_intelligence.py) must catch this and translate it into a 502.
    There is deliberately no deterministic fallback here: unlike
    prioritization or narrative generation, a failed extraction means
    there is no role to build a profile FROM at all, so degrading
    silently would mean persisting/returning a fabricated-empty profile
    as if it were real.
    """
    text_hash = _source_text_hash(raw_text)

    extracted = await extract_job_and_company(raw_text)  # JobIntelligenceExtractionError propagates to the caller
    job_extraction = extracted.job
    company_extraction = extracted.company

    enriched_required = await enrich_skills(job_extraction.required_skills, "required", db)
    enriched_implicit = await enrich_skills(job_extraction.implicit_skills, "implicit", db)
    enriched_nice = await enrich_skills(job_extraction.nice_to_have, "nice_to_have", db)

    resolved_role = role or job_extraction.role
    resolved_company = company or job_extraction.company

    # Seniority: deterministic-first, with an optional LLM-assist
    # refinement ONLY when the deterministic pass found nothing at all —
    # see seniority.py's detect_seniority_with_fallback. This step never
    # raises; a failed/ambiguous refinement silently keeps whatever the
    # deterministic pass returned.
    seniority = await detect_seniority_with_fallback(raw_text, resolved_role)

    resume_keywords = derive_resume_keywords(
        enriched_required, enriched_implicit,
        job_extraction.required_skills, job_extraction.implicit_skills,
        job_extraction.architecture_topics,
    )
    interview_focus_areas = derive_interview_focus_areas(
        enriched_required, job_extraction.architecture_topics, seniority,
    )

    total_requirements = len(enriched_required) + len(enriched_implicit) + len(job_extraction.architecture_topics)
    extraction_quality = _compute_extraction_quality(raw_text, total_requirements)

    # NOTE (fix): no longer sets a "capabilities" field — it used to be
    # set to a verbatim copy of architecture_topics with no independent
    # extraction and no consumer; see schemas/job_intelligence.py's
    # docstring on JobIntelligenceProfile for the full rationale.
    job_profile = JobIntelligenceProfile(
        role=resolved_role,
        company=resolved_company,
        enriched_required_skills=enriched_required,
        enriched_implicit_skills=enriched_implicit,
        enriched_nice_to_have=enriched_nice,
        architecture_topics=job_extraction.architecture_topics,
        seniority_signal=seniority,
        resume_keywords=resume_keywords,
        interview_focus_areas=interview_focus_areas,
        extraction_quality=extraction_quality,
        source_text_hash=text_hash,
    )
    company_profile = CompanyIntelligenceProfile(
        company=resolved_company,
        industry=company_extraction.industry,
        products_mentioned=company_extraction.products_mentioned,
        technologies_mentioned=company_extraction.technologies_mentioned,
        engineering_hints=company_extraction.engineering_hints,
        culture_hints=company_extraction.culture_hints,
        source_text_hash=text_hash,
    )

    now = datetime.now(timezone.utc)

    job_row = JobIntelligenceProfileRow(
        user_id=user_id, source_text_hash=text_hash,
        profile_json=job_profile.model_dump(mode="json"), created_at=now,
    )
    db.add(job_row)
    await db.flush()
    job_profile.id = str(job_row.id)
    job_profile.created_at = now.isoformat()

    company_row = CompanyIntelligenceProfileRow(
        user_id=user_id, source_text_hash=text_hash,
        profile_json=company_profile.model_dump(mode="json"), created_at=now,
    )
    db.add(company_row)
    await db.flush()
    company_profile.id = str(company_row.id)
    company_profile.created_at = now.isoformat()

    await db.commit()
    print(
        f"[TRACING] Job Intelligence + Company Intelligence persisted "
        f"(job_id={job_row.id}, company_id={company_row.id}).", flush=True,
    )

    return job_profile, company_profile


async def get_job_intelligence(db: AsyncSession, job_intelligence_id: UUID) -> JobIntelligenceProfile | None:
    result = await db.execute(
        select(JobIntelligenceProfileRow).where(JobIntelligenceProfileRow.id == job_intelligence_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    profile = JobIntelligenceProfile.model_validate(row.profile_json)
    profile.id = str(row.id)
    return profile