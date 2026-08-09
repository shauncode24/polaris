# backend/app/services/company_intelligence/reader.py
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_intelligence import CompanyIntelligenceProfileRow
from app.schemas.company_intelligence import CompanyIntelligenceProfile


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