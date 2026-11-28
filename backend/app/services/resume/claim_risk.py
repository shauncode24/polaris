"""The one claim-risk penalty table, used wherever projects are ranked, so a
change to how much an unsupported claim should matter happens once.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inference import ProjectClaimAuditReview

CLAIM_RISK_MULTIPLIER: dict[str, float] = {
    "high": 0.5,     # halve the score — significant unresolved risk
    "medium": 0.75,  # modest discount — partial unresolved risk
}


async def claim_risk_by_project_id(db: AsyncSession, project_ids: list) -> dict:
    """project_id -> "high"|"medium", for projects with an unresolved Claim
    Audit risk finding.
    """
    if not project_ids:
        return {}
    result = await db.execute(
        select(ProjectClaimAuditReview).where(ProjectClaimAuditReview.project_id.in_(project_ids))
    )
    risk_by_id = {}
    for row in result.scalars().all():
        level = (row.report_json or {}).get("narrative", {}).get("risk_level")
        if level in ("high", "medium"):
            risk_by_id[row.project_id] = level
    return risk_by_id


def apply_claim_risk_penalty(score: float, risk_level: str | None) -> float:
    multiplier = CLAIM_RISK_MULTIPLIER.get(risk_level, 1.0)
    return score * multiplier