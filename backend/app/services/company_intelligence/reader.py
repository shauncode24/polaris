from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_intelligence import CompanyIntelligenceProfileRow
from app.schemas.job_intelligence.company_intelligence import CompanyIntelligenceProfile


async def get_company_intelligence(db: AsyncSession, company_intelligence_id: UUID) -> CompanyIntelligenceProfile | None:
    result = await db.execute(
        select(CompanyIntelligenceProfileRow).where(CompanyIntelligenceProfileRow.id == company_intelligence_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    profile = CompanyIntelligenceProfile.model_validate(row.profile_json)
    profile.id = str(row.id)
    return profile


async def get_company_intelligence_by_source_hash(
    db: AsyncSession, user_id, source_text_hash: str
) -> CompanyIntelligenceProfile | None:
    """Job Intelligence and Company Intelligence rows share no FK between
    them by design (design doc revision — "no FK between them at the
    schema level so either can evolve independently"). This is the one
    place that reconnects a JobIntelligenceProfile back to its sibling
    Company Intelligence row, via the shared source_text_hash from the
    single combined extraction call that produced both.
    """
    result = await db.execute(
        select(CompanyIntelligenceProfileRow)
        .where(CompanyIntelligenceProfileRow.user_id == user_id)
        .where(CompanyIntelligenceProfileRow.source_text_hash == source_text_hash)
        .order_by(CompanyIntelligenceProfileRow.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    profile = CompanyIntelligenceProfile.model_validate(row.profile_json)
    profile.id = str(row.id)
    return profile