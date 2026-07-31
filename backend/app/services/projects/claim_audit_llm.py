import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.inference import ProjectClaimAuditReview
from app.prompts.project_claim_audit import CLAIM_AUDIT_SYSTEM_PROMPT
from app.schemas.project_intelligence import ClaimAuditFacts, ClaimAuditNarrative, ClaimAuditReport


def _fallback_narrative(facts: ClaimAuditFacts) -> ClaimAuditNarrative:
    if facts.unsupported_claims:
        risk = "high" if len(facts.unsupported_claims) > 1 else "medium"
        headline = f"{len(facts.unsupported_claims)} claimed technologies have no supporting evidence in the repo."
    elif facts.undersold_work:
        risk = "low"
        headline = "Your resume undersells this project's real engineering depth."
    else:
        risk = "low"
        headline = "Resume claims and verified repository evidence are aligned."

    return ClaimAuditNarrative(
        headline=headline,
        risk_level=risk,
        talking_points=[f"You have verified evidence for {t}." for t in facts.undersold_work[:3]],
        fixes=[f"Reconsider listing '{c}' unless you can point to real evidence." for c in facts.unsupported_claims[:3]],
    )


async def get_cached_claim_audit_report(db: AsyncSession, project_id) -> ClaimAuditReport | None:
    """Returns the last persisted claim audit for this project, or None
    if it's never been run. Callers should check this before calling
    generate_claim_audit_narrative() again, unless the project's stack/
    description or its matched GitHub facts have actually changed.
    """
    result = await db.execute(
        select(ProjectClaimAuditReview).where(ProjectClaimAuditReview.project_id == project_id)
    )
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
    degraded = False
    try:
        print(f"[TRACING] Requesting claim-audit narrative for '{facts.project_name}'...", flush=True)
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": CLAIM_AUDIT_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(facts_dict)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw claim-audit JSON:\n{content}", flush=True)
        narrative = ClaimAuditNarrative.model_validate(json.loads(content))
    except Exception as e:
        print(f"[TRACING] Claim-audit narrative degraded, using fallback: {e}", flush=True)
        narrative = _fallback_narrative(facts)
        degraded = True

    report = ClaimAuditReport(facts=facts, narrative=narrative, analysis_degraded=degraded)
    await _persist_claim_audit_report(db, user_id, project_id, report)
    return report