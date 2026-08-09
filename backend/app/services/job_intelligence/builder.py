# backend/app/services/job_intelligence/builder.py
"""Stages 9-11 — assembles and persists the complete JobIntelligenceProfile
+ CompanyIntelligenceProfile from ONE extraction call.

Extraction-quality heuristic additions (review findings #3/#12):
extraction_quality now also penalizes two specific silent-drop patterns
the review caught on a real JD — an "added advantage" / "nice to have"
phrase present in the text with nothing landing in nice_to_have, and an
experience/internship phrase present in the text with no structured
experience requirement extracted. These are keyword heuristics, not
proof the LLM got the *content* right — they only catch "a real textual
signal existed and nothing came out the other end matching it." See
normalization.py's module docstring for the deeper, more common cause
of missing required_skills entries (the resume-oriented classifier
silently dropping process/practice requirements), which this quality
score does not separately detect.
"""
import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_intelligence import CompanyIntelligenceProfileRow, JobIntelligenceProfileRow
from app.schemas.company_intelligence import CompanyIntelligenceProfile
from app.schemas.job_intelligence import ExtractionQuality, JobIntelligenceProfile, SeniorityLevel
from app.services.job_intelligence.extraction import JobIntelligenceExtractionError, extract_job_and_company
from app.services.job_intelligence.interview_focus import derive_interview_focus_areas
from app.services.job_intelligence.keywords import derive_resume_keyword_tiers, derive_resume_keywords
from app.services.job_intelligence.normalization import enrich_skill_requirements, enrich_skills
from app.services.job_intelligence.seniority import detect_seniority_with_fallback

__all__ = ["build_job_intelligence", "get_job_intelligence", "JobIntelligenceExtractionError"]

_ENTRY_LEVEL_TITLE_WORDS = ["trainee", "intern", "graduate trainee", "entry level", "entry-level"]

# Review findings #3/#12 — real textual signals that, if present with no
# matching structured output, mean extraction most likely silently
# dropped something rather than the JD genuinely having nothing to say.
_NICE_TO_HAVE_PHRASES = [
    "added advantage", "nice to have", "nice-to-have", "is a plus",
    "a plus", "bonus", "preferred", "good to have",
]
_EXPERIENCE_PHRASES = [
    "experience", "internship", "years of", "yrs of", "hands on", "hands-on",
]


def _source_text_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.strip().encode()).hexdigest()


def _detect_seniority_contradiction(
    seniority: SeniorityLevel, role_title: str | None, designation: str | None
) -> str | None:
    """Surfaced in extraction_quality as a confidence penalty (audit
    point #17). Note: seniority.py's apply_designation_override already
    prevents this contradiction from reaching the final seniority_signal
    at all — this check is pure defense-in-depth, so it still fires (and
    still gets reported) if that override logic is ever changed.
    """
    text_fields = " ".join(filter(None, [role_title, designation])).lower()
    if seniority.level in ("senior", "staff") and any(w in text_fields for w in _ENTRY_LEVEL_TITLE_WORDS):
        return (
            f"Seniority signal '{seniority.level}' conflicts with an apparent entry-level "
            f"title/designation ('{designation or role_title}')"
        )
    return None


def _compute_extraction_quality(
    raw_text: str,
    total_requirements: int,
    responsibilities: list[str],
    seniority: SeniorityLevel,
    role_title: str | None,
    designation: str | None,
    nice_to_have_count: int,
    has_experience_requirement: bool,
) -> ExtractionQuality:
    word_count = len(raw_text.split())
    lowered_text = raw_text.lower()
    reasons: list[str] = []
    score = 1.0

    if word_count < 80:
        score -= 0.4
        reasons.append(f"Job description is short (~{word_count} words)")
    if total_requirements < 3:
        score -= 0.3
        reasons.append(f"Only {total_requirements} requirement(s) were extracted")
    if not responsibilities and total_requirements > 0:
        score -= 0.15
        reasons.append("No explicit role responsibilities were extracted")

    contradiction = _detect_seniority_contradiction(seniority, role_title, designation)
    if contradiction:
        score -= 0.35
        reasons.append(contradiction)

    # NEW (review finding #3) — "microservices is an added advantage"
    # class of miss: a real preference-language phrase exists in the
    # text but nothing was captured in nice_to_have.
    if nice_to_have_count == 0 and any(p in lowered_text for p in _NICE_TO_HAVE_PHRASES):
        score -= 0.2
        reasons.append(
            "The text appears to mark something as preferred/an added advantage, but nothing was "
            "extracted into nice_to_have"
        )

    # NEW (review finding #1) — "hands-on experience through
    # internships/projects" class of miss: a real experience phrase
    # exists in the text but qualification_requirements.experience is null.
    if not has_experience_requirement and any(p in lowered_text for p in _EXPERIENCE_PHRASES):
        score -= 0.15
        reasons.append(
            "The text appears to reference candidate experience, but no structured experience "
            "requirement was extracted"
        )

    score = max(0.0, min(1.0, score))
    if not reasons:
        reasons.append("Job description had enough detail to extract confidently")
    label = "High" if score >= 0.75 else ("Medium" if score >= 0.4 else "Low")
    return ExtractionQuality(score=round(score, 2), label=label, reasons=reasons)


async def build_job_intelligence(
    db: AsyncSession, user_id, raw_text: str, company: str | None = None, role: str | None = None,
) -> tuple[JobIntelligenceProfile, CompanyIntelligenceProfile]:
    text_hash = _source_text_hash(raw_text)

    extracted = await extract_job_and_company(raw_text)  # JobIntelligenceExtractionError propagates
    job_extraction = extracted.job
    company_extraction = extracted.company

    enriched_required = await enrich_skill_requirements(job_extraction.required_skills, "required", db)
    enriched_implicit = await enrich_skills(job_extraction.implicit_skills, "implicit", db)
    enriched_nice = await enrich_skill_requirements(job_extraction.nice_to_have, "nice_to_have", db)

    resolved_role = role or job_extraction.role or job_extraction.role_identity.title
    resolved_company = company or job_extraction.company

    # Designation is passed in explicitly now — this is what lets
    # apply_designation_override catch "Engineering Trainee" even if the
    # years-regex or LLM-assist path gets it wrong upstream.
    seniority = await detect_seniority_with_fallback(
        raw_text, resolved_role, designation=job_extraction.role_identity.designation,
    )

    raw_required = [s.skill for s in job_extraction.required_skills]
    raw_implicit = [s.skill for s in job_extraction.implicit_skills]
    raw_nice_to_have = [s.skill for s in job_extraction.nice_to_have]

    resume_keywords = derive_resume_keywords(
        enriched_required, enriched_implicit, raw_required, raw_implicit, job_extraction.architecture_topics,
    )
    resume_keyword_tiers = derive_resume_keyword_tiers(
        enriched_required, enriched_implicit, enriched_nice,
        raw_required, raw_implicit, raw_nice_to_have,
        job_extraction.architecture_topics,
    )
    explicit_focus, inferred_focus, combined_focus = derive_interview_focus_areas(
        enriched_required, job_extraction.architecture_topics, seniority,
    )

    total_requirements = (
        len(enriched_required) + len(enriched_implicit) + len(job_extraction.architecture_topics)
    )
    extraction_quality = _compute_extraction_quality(
        raw_text, total_requirements, job_extraction.responsibilities, seniority,
        resolved_role, job_extraction.role_identity.designation,
        nice_to_have_count=len(enriched_nice),
        has_experience_requirement=job_extraction.qualification_requirements.experience is not None,
    )

    job_profile = JobIntelligenceProfile(
        role=resolved_role,
        company=resolved_company,
        role_identity=job_extraction.role_identity,
        job_purpose=job_extraction.job_purpose or "",
        responsibilities=job_extraction.responsibilities,
        enriched_required_skills=enriched_required,
        enriched_implicit_skills=enriched_implicit,
        enriched_nice_to_have=enriched_nice,
        capabilities=job_extraction.capabilities,
        architecture_topics=job_extraction.architecture_topics,
        qualification_requirements=job_extraction.qualification_requirements,
        seniority_signal=seniority,
        resume_keywords=resume_keywords,
        resume_keyword_tiers=resume_keyword_tiers,
        interview_focus_areas=combined_focus,
        interview_focus={"explicit": explicit_focus, "inferred": inferred_focus},
        extraction_quality=extraction_quality,
        source_text_hash=text_hash,
    )
    company_profile = CompanyIntelligenceProfile(
        company=resolved_company,
        industry=company_extraction.industry,
        domain=company_extraction.domain,
        products_mentioned=company_extraction.products_mentioned,
        technologies_mentioned=company_extraction.technologies_mentioned,
        engineering_hints=company_extraction.engineering_hints,
        company_signals=company_extraction.company_signals,
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
        f"(job_id={job_row.id}, company_id={company_row.id}, "
        f"extraction_quality={extraction_quality.label}, seniority={seniority.level}).",
        flush=True,
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