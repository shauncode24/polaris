"""Readers for the stored comparison between a user's evidence and one
job intelligence profile (GapAnalysisResultRow).

This is the single place that answers "how does this user match that
job", so every consumer (career planner, identity, projects ranking,
resume page, the job list) reads the same row.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_intelligence import GapAnalysisResultRow


async def get_latest_gap_result(
    db: AsyncSession, user_id, job_intelligence_id=None
) -> GapAnalysisResultRow | None:
    """Most recent gap analysis for this user. When `job_intelligence_id`
    is given, restricts to that job; otherwise returns the latest across
    all of the user's jobs.
    """
    stmt = select(GapAnalysisResultRow).where(GapAnalysisResultRow.user_id == user_id)
    if job_intelligence_id is not None:
        stmt = stmt.where(GapAnalysisResultRow.job_intelligence_id == job_intelligence_id)
    stmt = stmt.order_by(GapAnalysisResultRow.created_at.desc()).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_latest_gap_results_by_job(db: AsyncSession, user_id) -> dict:
    """{job_intelligence_id: latest GapAnalysisResultRow} for every job
    this user has analysed. One query, newest row wins per job.
    """
    result = await db.execute(
        select(GapAnalysisResultRow)
        .where(GapAnalysisResultRow.user_id == user_id)
        .order_by(GapAnalysisResultRow.created_at.desc())
    )
    latest: dict = {}
    for row in result.scalars().all():
        latest.setdefault(row.job_intelligence_id, row)
    return latest
