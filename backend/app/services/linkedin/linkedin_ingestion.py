import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.facts import Education, Experience
from app.models.inference import SkillEvidence
from app.models.linkedin import LinkedInProfile
from app.prompts.linkedin.extraction import LINKEDIN_EXTRACTION_SYSTEM_PROMPT
from app.schemas.linkedin.linkedin import ExtractedLinkedInProfile, LinkedInIngestResult
from app.services.projects.linking import normalize_name
from app.services.resume.confidence import WEIGHTS
from app.services.resume.skill_classifier import resolve_skills
from app.services.user_helpers import get_or_create_skill

logger = logging.getLogger(__name__)

LINKEDIN_EVIDENCE_SOURCE_TYPE = "linkedin_profile"


class LinkedInExtractionError(Exception):
    """Raised when the LinkedIn extraction LLM call fails or returns
    something we can't validate. Same graceful-degradation boundary as
    JobIntelligenceExtractionError — there is no safe deterministic
    fallback for free-text extraction, so callers surface this as a
    real failure (HTTP 502) rather than silently ingesting garbage.
    """


async def extract_linkedin_profile(raw_text: str) -> ExtractedLinkedInProfile:
    logger.debug("Extracting LinkedIn profile data (length: %d chars)...", len(raw_text))
    try:
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": LINKEDIN_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        return ExtractedLinkedInProfile.model_validate(json.loads(content))
    except Exception as e:
        raise LinkedInExtractionError(f"LinkedIn extraction LLM call failed: {e}") from e


async def _existing_experience_keys(db: AsyncSession, user_id) -> set[str]:
    result = await db.execute(select(Experience.role, Experience.company).where(Experience.user_id == user_id))
    return {f"{normalize_name(r)}@{normalize_name(c)}" for r, c in result.all()}


async def _existing_education_keys(db: AsyncSession, user_id) -> set[str]:
    result = await db.execute(select(Education.institution, Education.degree).where(Education.user_id == user_id))
    return {f"{normalize_name(i)}@{normalize_name(d or '')}" for i, d in result.all()}


async def ingest_linkedin_profile(db: AsyncSession, user, raw_text: str) -> LinkedInIngestResult:
    """Reconciles pasted LinkedIn content into the SAME Experience /
    Education / SkillEvidence tables Resume ingestion already writes to
    — LinkedIn is deliberately NOT a parallel identity system (per
    Phase 4 scope: "a source of evidence, not an independent identity
    system"). Dedup uses the exact same normalize_name()-based key every
    other module in this codebase already uses (profile.py,
    identity_builder.py, career_planner/context_builder.py) — a
    role+company or institution+degree already present from a resume
    upload is never duplicated here, only reinforced via SkillEvidence.
    """
    extraction = await extract_linkedin_profile(raw_text)

    profile_row = LinkedInProfile(
        user_id=user.id,
        raw_text=raw_text,
        parsed_json=extraction.model_dump(mode="json"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(profile_row)
    await db.flush()

    existing_exp_keys = await _existing_experience_keys(db, user.id)
    experiences_created = experiences_deduped = 0
    for exp in extraction.experience:
        if not exp.role or not exp.company:
            continue
        key = f"{normalize_name(exp.role)}@{normalize_name(exp.company)}"
        if key in existing_exp_keys:
            experiences_deduped += 1
            continue
        existing_exp_keys.add(key)
        db.add(Experience(
            user_id=user.id, resume_id=None, role=exp.role, company=exp.company,
            start_date=None, end_date=None, stack=[], bullets=exp.bullets,
            source="linkedin", created_at=datetime.now(timezone.utc),
        ))
        experiences_created += 1

    existing_edu_keys = await _existing_education_keys(db, user.id)
    education_created = education_deduped = 0
    for edu in extraction.education:
        if not edu.institution:
            continue
        key = f"{normalize_name(edu.institution)}@{normalize_name(edu.degree or '')}"
        if key in existing_edu_keys:
            education_deduped += 1
            continue
        existing_edu_keys.add(key)
        db.add(Education(
            user_id=user.id, resume_id=None, institution=edu.institution, degree=edu.degree,
            field_of_study=edu.field_of_study, start_date=None, end_date=None, is_current=False,
            details=[], source="linkedin", created_at=datetime.now(timezone.utc),
        ))
        education_created += 1

    # --- Skill evidence: same weighted-evidence pattern as resume/github/
    # leetcode, tagged with its own source_type so a skill backed only by
    # a LinkedIn mention is still visible everywhere confidence is
    # computed, but distinguishable in provenance from stronger evidence.
    raw_skill_strings = set(extraction.skills)
    resolved = await resolve_skills(raw_skill_strings, db) if raw_skill_strings else {}
    skills_processed = 0
    for raw, canonical in resolved.items():
        if canonical is None:
            continue
        skill = await get_or_create_skill(db, canonical, raw)
        existing_ev = await db.execute(
            select(SkillEvidence).where(
                SkillEvidence.user_id == user.id,
                SkillEvidence.skill_id == skill.id,
                SkillEvidence.source_type == LINKEDIN_EVIDENCE_SOURCE_TYPE,
            )
        )
        if existing_ev.scalar_one_or_none() is not None:
            continue
        db.add(SkillEvidence(
            user_id=user.id, skill_id=skill.id, source_type=LINKEDIN_EVIDENCE_SOURCE_TYPE,
            source_id=profile_row.id, weight=WEIGHTS.get("linkedin", 0.20),
        ))
        skills_processed += 1

    await db.flush()
    await db.commit()

    logger.info(
        "LinkedIn profile ingested (user_id=%s, experiences=+%d/~%d, education=+%d/~%d, skills=+%d)",
        user.id, experiences_created, experiences_deduped, education_created, education_deduped, skills_processed,
    )

    return LinkedInIngestResult(
        linkedin_profile_id=str(profile_row.id),
        experiences_created=experiences_created,
        education_created=education_created,
        skills_processed=skills_processed,
        experiences_deduped=experiences_deduped,
        education_deduped=education_deduped,
    )


async def get_latest_linkedin_profile(db: AsyncSession, user_id) -> LinkedInProfile | None:
    result = await db.execute(
        select(LinkedInProfile)
        .where(LinkedInProfile.user_id == user_id)
        .order_by(LinkedInProfile.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()