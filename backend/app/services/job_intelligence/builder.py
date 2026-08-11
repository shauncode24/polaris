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
from app.schemas.job_intelligence.company_intelligence import CompanyIntelligenceProfile
from app.schemas.job_intelligence.job_intelligence import ExtractionQuality, JobIntelligenceProfile, SeniorityLevel
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


_ARCHITECTURE_KEYWORDS = [
    "scalab", "modular", "performance", "reliab", "availab",
    "non-functional", "nfr", "latency", "throughput", "fault",
]
_COMPANY_CONTEXT_KEYWORDS = [
    "about us", "about the company", "who we are", "our story", "our mission",
    "our values", "work with us", "culture", "diversity", "inclusion", "dei",
    "great place to work", "recognition", "award",
]


def _compute_extraction_quality(
    raw_text: str,
    total_requirements: int,
    responsibilities: list[str],
    seniority: SeniorityLevel,
    role_title: str | None,
    designation: str | None,
    nice_to_have_count: int,
    has_experience_requirement: bool,
    capabilities: list[str] | None = None,
    architecture_topics: list[str] | None = None,
    company_signals_empty: bool = False,
    has_company_identity: bool = False,
    has_company_industry: bool = False,
    has_company_domain: bool = False,
    has_company_products: bool = False,
    has_education: bool = False,
) -> ExtractionQuality:
    word_count = len(raw_text.split())
    lowered_text = raw_text.lower()
    reasons: list[str] = []

    # ── Job completeness ──────────────────────────────────────────────────
    # 7 checkable job fields; each one that's missing counts against the score.
    job_checks = {
        "requirements": total_requirements >= 3,
        "responsibilities": bool(responsibilities),
        "capabilities": bool(capabilities),
        "architecture_topics": bool(architecture_topics),
        "nice_to_have": nice_to_have_count > 0 or not any(p in lowered_text for p in _NICE_TO_HAVE_PHRASES),
        "experience": has_experience_requirement or not any(p in lowered_text for p in _EXPERIENCE_PHRASES),
        "education": has_education or word_count < 80,  # short JDs may not have education
    }
    job_completeness = sum(1 for v in job_checks.values() if v) / len(job_checks)

    if total_requirements < 3:
        reasons.append(f"Only {total_requirements} requirement(s) were extracted")
    if not responsibilities:
        reasons.append("No explicit role responsibilities were extracted")
    if not capabilities and responsibilities:
        reasons.append("Capabilities were not extracted despite the JD containing responsibilities")
    if not architecture_topics and any(kw in lowered_text for kw in _ARCHITECTURE_KEYWORDS):
        reasons.append("Architecture topics were not extracted despite architecture-relevant language")
    if nice_to_have_count == 0 and any(p in lowered_text for p in _NICE_TO_HAVE_PHRASES):
        reasons.append(
            "The text appears to mark something as preferred/an added advantage, but nothing was "
            "extracted into nice_to_have"
        )
    if not has_experience_requirement and any(p in lowered_text for p in _EXPERIENCE_PHRASES):
        reasons.append(
            "The text appears to reference candidate experience, but no structured experience "
            "requirement was extracted"
        )

    # ── Company completeness ──────────────────────────────────────────────
    # Only penalize when there's evidence the document actually has company context.
    has_company_text = any(kw in lowered_text for kw in _COMPANY_CONTEXT_KEYWORDS)
    if has_company_text:
        company_checks = {
            "identity": has_company_identity,
            "industry": has_company_industry,
            "domain": has_company_domain,
            "products": has_company_products,
            "signals": not company_signals_empty,
        }
        company_completeness = sum(1 for v in company_checks.values() if v) / len(company_checks)
        if not has_company_identity:
            reasons.append("Company name was not extracted despite company context in the document")
        if company_signals_empty:
            reasons.append(
                "Company signals (culture, values, DEI, recognition) were not extracted despite "
                "apparent company overview content in the document"
            )
    else:
        # No company context detected — full marks; nothing to extract
        company_completeness = 1.0

    # ── Seniority contradiction ───────────────────────────────────────────
    seniority_penalty = 0.0
    contradiction = _detect_seniority_contradiction(seniority, role_title, designation)
    if contradiction:
        seniority_penalty = 0.15
        reasons.append(contradiction)

    # ── Short JD ─────────────────────────────────────────────────────────
    if word_count < 80:
        reasons.append(f"Job description is short (~{word_count} words)")

    # ── Overall composite ─────────────────────────────────────────────────
    # Weighted: job 55%, company 35%, seniority integrity 10%
    overall = (job_completeness * 0.55) + (company_completeness * 0.35) + ((1.0 - seniority_penalty) * 0.10)
    overall = max(0.0, min(1.0, overall))

    if not reasons:
        reasons.append("Job description had enough detail to extract confidently")
    label = "High" if overall >= 0.75 else ("Medium" if overall >= 0.4 else "Low")
    return ExtractionQuality(
        score=round(overall, 2),
        job_completeness=round(job_completeness, 2),
        company_completeness=round(company_completeness, 2),
        label=label,
        reasons=reasons,
    )


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
    cs = company_extraction.company_signals
    company_signals_empty = (
        not cs.culture and not cs.values and not cs.work_environment
        and not cs.learning_development and not cs.diversity_inclusion and not cs.recognition
    )
    extraction_quality = _compute_extraction_quality(
        raw_text, total_requirements, job_extraction.responsibilities, seniority,
        resolved_role, job_extraction.role_identity.designation,
        nice_to_have_count=len(enriched_nice),
        has_experience_requirement=job_extraction.qualification_requirements.experience is not None,
        capabilities=job_extraction.capabilities,
        architecture_topics=job_extraction.architecture_topics,
        company_signals_empty=company_signals_empty,
        has_company_identity=bool(resolved_company),
        has_company_industry=bool(company_extraction.industry),
        has_company_domain=bool(company_extraction.domain),
        has_company_products=bool(company_extraction.products_mentioned),
        has_education=bool(job_extraction.qualification_requirements.education),
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