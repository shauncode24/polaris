"""Saving and loading tailored resumes. Each save of a new resume for a job is
a new version; every lookup is limited to the user's own.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_intelligence import JobIntelligenceProfileRow
from app.models.tailored_resume import RESUME_DRAFT, TailoredResume
from app.schemas.resume.tailored import TailoredResumeDocument


def document_of(row: TailoredResume) -> TailoredResumeDocument:
    return TailoredResumeDocument.model_validate(row.content_json)


async def save_new_version(
    db: AsyncSession, user_id, job_intelligence_id, document: TailoredResumeDocument,
) -> TailoredResume | None:
    """Stores `document` as the next version for this job. None when the user
    has no such job.
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
        select(func.max(TailoredResume.version)).where(
            TailoredResume.user_id == user_id, TailoredResume.job_intelligence_id == job_intelligence_id,
        )
    )
    row_id = uuid.uuid4()
    await db.execute(insert(TailoredResume).values(
        id=row_id, user_id=user_id, job_intelligence_id=job_intelligence_id,
        version=(latest or 0) + 1, status=RESUME_DRAFT,
        content_json=document.model_dump(mode="json"), created_at=datetime.now(timezone.utc),
    ))
    await db.commit()
    return await db.get(TailoredResume, row_id)


async def get_version(
    db: AsyncSession, user_id, job_intelligence_id, version: int | None = None,
) -> TailoredResume | None:
    """One version of the user's resume for a job; the newest when `version`
    is not given.
    """
    query = select(TailoredResume).where(
        TailoredResume.user_id == user_id, TailoredResume.job_intelligence_id == job_intelligence_id,
    )
    if version is not None:
        query = query.where(TailoredResume.version == version)
    return await db.scalar(query.order_by(TailoredResume.version.desc()).limit(1))
