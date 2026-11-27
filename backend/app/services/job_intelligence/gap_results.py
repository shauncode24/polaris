"""Readers for the stored comparison between a user's evidence and one
job intelligence profile (GapAnalysisResultRow).

This is the single place that answers "how does this user match that
job", so every consumer (career planner, identity, projects ranking,
resume page, the job list) reads the same row.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_intelligence import GapAnalysisResultRow
from app.schemas.skill_gap.skill_gap import REPORT_VERSION
from app.services.evidence.state import evidence_cutoff


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


def _is_current(row: GapAnalysisResultRow, cutoff) -> bool:
    if (row.report_json or {}).get("evidence_version", 0) < REPORT_VERSION:
        return False
    return cutoff is None or row.created_at >= cutoff


async def is_current_gap_result(db: AsyncSession, user_id, row: GapAnalysisResultRow) -> bool:
    """False when the stored comparison should be rebuilt: it predates the
    user's last evidence change, or it was written in an older report format.
    """
    return _is_current(row, await evidence_cutoff(db, user_id))


async def get_current_gap_results_by_job(db: AsyncSession, user_id) -> dict:
    """{job_intelligence_id: latest GapAnalysisResultRow} for every job
    whose latest comparison is still current. An outdated score is left out
    rather than shown as if it were today's.
    """
    result = await db.execute(
        select(GapAnalysisResultRow)
        .where(GapAnalysisResultRow.user_id == user_id)
        .order_by(GapAnalysisResultRow.created_at.desc())
    )
    latest: dict = {}
    for row in result.scalars().all():
        latest.setdefault(row.job_intelligence_id, row)
    cutoff = await evidence_cutoff(db, user_id)
    return {job_id: row for job_id, row in latest.items() if _is_current(row, cutoff)}
