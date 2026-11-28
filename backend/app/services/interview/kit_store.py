"""Saving and loading interview kits. Each newly generated kit for a job is a new
version; every lookup is limited to the user's own.
"""
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interview_kit import InterviewKit, InterviewQuestion
from app.models.job_intelligence import JobIntelligenceProfileRow
from app.schemas.interview.kit import InterviewKitDraft


@dataclass(frozen=True)
class SavedKit:
    kit: InterviewKit
    questions: list[InterviewQuestion]  # in the kit's order


async def save_new_kit(
    db: AsyncSession, user_id, job_intelligence_id, draft: InterviewKitDraft,
) -> SavedKit | None:
    """Stores `draft` as the next version for this job. None when the user has
    no such job.
    """
    owned = await db.scalar(
        # Locked until commit, so two saves for one job take turns and can't
        # pick the same version number.
        select(JobIntelligenceProfileRow.id)
        .where(JobIntelligenceProfileRow.id == job_intelligence_id, JobIntelligenceProfileRow.user_id == user_id)
        .with_for_update()
    )
    if owned is None:
        return None

    latest = await db.scalar(
        select(func.max(InterviewKit.version)).where(
            InterviewKit.user_id == user_id, InterviewKit.job_intelligence_id == job_intelligence_id,
        )
    )
    kit = InterviewKit(
        id=uuid.uuid4(), user_id=user_id, job_intelligence_id=job_intelligence_id,
        version=(latest or 0) + 1, seniority=draft.seniority, notice=draft.notice,
        evidence_mapped_at=draft.evidence_mapped_at, evidence_notice=draft.evidence_notice,
    )
    db.add(kit)
    await db.flush()  # the questions refer to it
    db.add_all([
        InterviewQuestion(kit_id=kit.id, position=position, **question.model_dump(mode="json"))
        for position, question in enumerate(draft.questions)
    ])
    await db.commit()
    return await get_kit(db, user_id, job_intelligence_id, kit.version)


async def list_versions(db: AsyncSession, user_id, job_intelligence_id) -> list[int]:
    """The version numbers of the user's kit for a job, newest first."""
    result = await db.scalars(
        select(InterviewKit.version)
        .where(InterviewKit.user_id == user_id, InterviewKit.job_intelligence_id == job_intelligence_id)
        .order_by(InterviewKit.version.desc())
    )
    return list(result)


async def get_kit(
    db: AsyncSession, user_id, job_intelligence_id, version: int | None = None,
) -> SavedKit | None:
    """One version of the user's kit for a job; the newest when `version` is not
    given.
    """
    query = select(InterviewKit).where(
        InterviewKit.user_id == user_id, InterviewKit.job_intelligence_id == job_intelligence_id,
    )
    if version is not None:
        query = query.where(InterviewKit.version == version)
    kit = await db.scalar(query.order_by(InterviewKit.version.desc()).limit(1))
    if kit is None:
        return None
    questions = await db.scalars(
        select(InterviewQuestion).where(InterviewQuestion.kit_id == kit.id).order_by(InterviewQuestion.position)
    )
    return SavedKit(kit, list(questions))
