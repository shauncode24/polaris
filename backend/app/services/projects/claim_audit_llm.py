import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import Prompt, llm_json
from app.services.evidence.state import evidence_cutoff
from app.models.inference import ProjectClaimAuditReview
from app.prompts.projects.project_claim_audit import CLAIM_AUDIT_SYSTEM_PROMPT
from app.schemas.projects.project_intelligence import ClaimAuditFacts, ClaimAuditNarrative, ClaimAuditReport

logger = logging.getLogger(__name__)


def _fallback_narrative(facts: ClaimAuditFacts) -> ClaimAuditNarrative:
    if facts.unsupported_claims:
        headline = f"{len(facts.unsupported_claims)} claimed technologies have no supporting evidence in the repo."
    elif facts.undersold_work:
        headline = "Your resume undersells this project's real engineering depth."
    else:
        headline = "Resume claims and verified repository evidence are aligned."

    return ClaimAuditNarrative(
        headline=headline,
        risk_level=facts.risk_level,
        talking_points=[f"You have verified evidence for {t}." for t in facts.undersold_work[:3]],
        fixes=[f"Reconsider listing '{c}' unless you can point to real evidence." for c in facts.unsupported_claims[:3]],
    )


async def get_cached_claim_audit_report(db: AsyncSession, user_id, project_id) -> ClaimAuditReport | None:
    """Returns the last persisted claim audit for this project, or None
    if it's never been run. Callers should check this before calling
    generate_claim_audit_narrative() again, unless the project's stack/
    description or its matched GitHub facts have actually changed.
    """
    stmt = (
        select(ProjectClaimAuditReview)
        .where(ProjectClaimAuditReview.user_id == user_id)
        .where(ProjectClaimAuditReview.project_id == project_id)
    )
    cutoff = await evidence_cutoff(db, user_id)
    if cutoff is not None:  # a report built before the evidence last changed is out of date
        stmt = stmt.where(ProjectClaimAuditReview.created_at >= cutoff)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return ClaimAuditReport.model_validate(row.report_json)


async def _persist_claim_audit_report(db: AsyncSession, user_id, project_id, report: ClaimAuditReport) -> None:
    payload = report.model_dump(mode="json")
    stmt = (
        pg_insert(ProjectClaimAuditReview)
        .values(
            user_id=user_id, project_id=project_id, report_json=payload,
            created_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            constraint="uq_claim_audit_project",
            set_={"report_json": payload, "created_at": datetime.now(timezone.utc)},
        )
    )
    await db.execute(stmt)
    await db.commit()


async def generate_claim_audit_narrative(
    db: AsyncSession, user_id, project_id, facts_dict: dict
) -> ClaimAuditReport:
    facts = ClaimAuditFacts(**facts_dict)
    logger.debug("Requesting claim-audit narrative for '%s'...", facts.project_name)
    reply = await llm_json(
        Prompt(CLAIM_AUDIT_SYSTEM_PROMPT, facts_dict), ClaimAuditNarrative,
        lambda: _fallback_narrative(facts), label="claim_audit", temperature=0.2,
        expect=("headline", "talking_points", "fixes"),
    )
    narrative, degraded = reply.value, reply.degraded
    if not degraded:
        narrative.risk_level = facts.risk_level  # deterministic fact — never LLM-decided

    report = ClaimAuditReport(facts=facts, narrative=narrative, analysis_degraded=degraded)
    await _persist_claim_audit_report(db, user_id, project_id, report)
    return report