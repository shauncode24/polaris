"""The user's saved jobs: which one they are preparing for, how they compare,
and removing them.
"""
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goals import Goal
from app.models.interview_kit import InterviewKit
from app.models.job_intelligence import (
    CompanyIntelligenceProfileRow,
    GapAnalysisResultRow,
    JobIntelligenceProfileRow,
)
from app.models.tailored_resume import TailoredResume
from app.schemas.job_intelligence.library import ComparedJob, ComparedSkill, JobComparison
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.skill_gap.category_breakdown import compute_overall_match
from app.services.skill_gap.comparison import load_evidence_view, match_requirements

MAX_COMPARED_JOBS = 4

_BAND_ORDER = {"required": 0, "implicit": 1, "nice_to_have": 2}


async def get_primary_job_id(db: AsyncSession, user_id) -> UUID | None:
    result = await db.execute(
        select(JobIntelligenceProfileRow.id)
        .where(JobIntelligenceProfileRow.user_id == user_id)
        .where(JobIntelligenceProfileRow.is_primary)
    )
    return result.scalar_one_or_none()


async def _owned_row(db: AsyncSession, user_id, job_id: UUID) -> JobIntelligenceProfileRow | None:
    result = await db.execute(
        select(JobIntelligenceProfileRow)
        .where(JobIntelligenceProfileRow.id == job_id)
        .where(JobIntelligenceProfileRow.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def set_primary(db: AsyncSession, user_id, job_id: UUID, primary: bool = True) -> bool:
    """Makes this job the user's primary target, replacing any other, or
    stops it being one. False when the user has no such job.
    """
    row = await _owned_row(db, user_id, job_id)
    if row is None:
        return False
    if primary:
        # Released first: the database allows only one primary per user.
        await db.execute(
            update(JobIntelligenceProfileRow)
            .where(JobIntelligenceProfileRow.user_id == user_id)
            .where(JobIntelligenceProfileRow.id != job_id)
            .where(JobIntelligenceProfileRow.is_primary)
            .values(is_primary=False)
        )
    row.is_primary = primary
    await db.commit()
    return True


async def delete_job(db: AsyncSession, user_id, job_id: UUID) -> bool:
    """Removes a job and everything computed for it. Goals that targeted it
    are kept, without the link. False when the user has no such job.
    """
    row = await _owned_row(db, user_id, job_id)
    if row is None:
        return False
    source_hash = row.source_text_hash

    await db.execute(
        update(Goal).where(Goal.user_id == user_id, Goal.job_intelligence_id == job_id)
        .values(job_intelligence_id=None)
    )
    for model in (TailoredResume, InterviewKit, GapAnalysisResultRow):
        await db.execute(delete(model).where(model.user_id == user_id, model.job_intelligence_id == job_id))
    await db.delete(row)
    await db.flush()

    # Company profiles are matched to jobs by the posting's text, so they go
    # only when no other saved copy of the same posting remains.
    same_posting = await db.execute(
        select(JobIntelligenceProfileRow.id)
        .where(JobIntelligenceProfileRow.user_id == user_id)
        .where(JobIntelligenceProfileRow.source_text_hash == source_hash)
        .limit(1)
    )
    if same_posting.scalar_one_or_none() is None:
        await db.execute(
            delete(CompanyIntelligenceProfileRow)
            .where(CompanyIntelligenceProfileRow.user_id == user_id)
            .where(CompanyIntelligenceProfileRow.source_text_hash == source_hash)
        )
    await db.commit()
    return True


async def compare_jobs(db: AsyncSession, user_id, job_ids: list[UUID]) -> JobComparison | None:
    """Matches the user's current evidence against each job. Computed fresh,
    with no LLM prioritisation or narrative. None when any job isn't theirs.
    """
    profiles, primary_id = [], await get_primary_job_id(db, user_id)
    for job_id in job_ids:
        profile = await get_job_intelligence(db, user_id, job_id)
        if profile is None:
            return None
        profiles.append(profile)

    view = await load_evidence_view(db, user_id, {c for p in profiles for c in p.canonical_skills_map})

    jobs: list[ComparedJob] = []
    status: dict[str, str] = {}
    bands: dict[str, dict[str, str]] = {}
    for profile in profiles:
        requirements = profile.canonical_skills_map
        have, partial, missing = match_requirements(requirements, view)
        for label, group in (("have", have), ("partial", partial), ("missing", missing)):
            status.update({entry.skill: label for entry in group})
        for skill, band in requirements.items():
            bands.setdefault(skill, {})[profile.id] = band
        jobs.append(ComparedJob(
            id=profile.id, role=profile.role, company=profile.company,
            seniority_level=profile.seniority_signal.level,
            is_primary=profile.id == str(primary_id),
            overall_match=compute_overall_match(requirements, have, partial, missing) if requirements else None,
        ))

    # What most of the compared jobs ask for comes first, then what they insist on.
    ordered = sorted(
        bands,
        key=lambda s: (-len(bands[s]), min(_BAND_ORDER.get(b, 2) for b in bands[s].values()), s),
    )
    return JobComparison(
        jobs=jobs,
        skills=[ComparedSkill(skill=s, status=status[s], bands=bands[s]) for s in ordered],
    )
