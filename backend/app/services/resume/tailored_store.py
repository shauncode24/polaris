"""Saving and loading tailored resumes. Each newly generated resume for a job is
a new version, which the user's choices then change in place; every lookup is
limited to the user's own.
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
    db: AsyncSession, user_id, job_intelligence_id, version: int | None = None, *, for_update: bool = False,
) -> TailoredResume | None:
    """One version of the user's resume for a job; the newest when `version`
    is not given. With `for_update` it is locked until the next commit.
    """
    query = select(TailoredResume).where(
        TailoredResume.user_id == user_id, TailoredResume.job_intelligence_id == job_intelligence_id,
    )
    if version is not None:
        query = query.where(TailoredResume.version == version)
    query = query.order_by(TailoredResume.version.desc()).limit(1)
    return await db.scalar(query.with_for_update() if for_update else query)


async def list_versions(db: AsyncSession, user_id, job_intelligence_id) -> list[int]:
    """The version numbers of the user's resume for a job, newest first."""
    result = await db.scalars(
        select(TailoredResume.version)
        .where(TailoredResume.user_id == user_id, TailoredResume.job_intelligence_id == job_intelligence_id)
        .order_by(TailoredResume.version.desc())
    )
    return list(result)


async def save_document(db: AsyncSession, row: TailoredResume, document: TailoredResumeDocument) -> None:
    """Replaces the content of a version the caller has loaded as the user's."""
    # Validated again: it may have been changed field by field since it was read.
    checked = TailoredResumeDocument.model_validate(document.model_dump())
    row.content_json = checked.model_dump(mode="json")
    await db.commit()
