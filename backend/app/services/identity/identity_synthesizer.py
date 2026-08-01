import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.inference import EngineeringIdentity
from app.prompts.identity_synthesis import IDENTITY_SYNTHESIS_SYSTEM_PROMPT
from app.schemas.engineering_identity import (
    EngineeringIdentityReport,
    IdentityFacts,
    IdentityLLMOutput,
)
from app.services.identity.identity_builder import build_identity_facts


class IdentitySynthesisError(Exception):
    """Raised when the synthesis LLM call fails or returns something we
    can't validate. Callers fall back to a deterministic template
    instead of crashing the whole report.
    """


def _fallback_narrative(facts: IdentityFacts) -> IdentityLLMOutput:
    top_names = [s["skill"].title() for s in facts.top_skills[:4]]
    best_role = facts.role_fit[0] if facts.role_fit else None

    summary_parts = []
    if best_role:
        summary_parts.append(
            f"Your strongest evidenced fit is {best_role['role']} (rated {best_role['rating']}/5)."
        )
    if top_names:
        summary_parts.append(f"Your most-evidenced skills are {', '.join(top_names)}.")
    if facts.resume_score is not None:
        summary_parts.append(f"Resume score is currently {facts.resume_score}/100.")
    if facts.engineering_quadrant:
        summary_parts.append(f"Engineering placement: {facts.engineering_quadrant['quadrant_label']}.")

    gaps = []
    if facts.coverage_gaps.get("github_gaps"):
        gaps.append(f"{len(facts.coverage_gaps['github_gaps'])} GitHub-evidenced skill(s) missing from your resume")
    if facts.timeline_plausibility_notes:
        gaps.append(f"{len(facts.timeline_plausibility_notes)} timeline note(s) worth reviewing")
    if facts.claim_risk_details:
        gaps.append(f"{len(facts.claim_risk_details)} project(s) with unresolved claim-vs-implementation risk")

    return IdentityLLMOutput(
        headline=best_role["role"] if best_role else "Engineering profile",
        summary=" ".join(summary_parts) or "Not enough evidence yet to summarize your profile.",
        strongest_signals=top_names,
        biggest_gaps=gaps,
        contradictions=[
            f"{c['project']}: {c['headline']}" for c in facts.claim_risk_details[:2]
        ],
        recommended_focus=(
            "Sync GitHub and LeetCode, then re-run this once more evidence exists."
            if not top_names else ""
        ),
    )


async def generate_engineering_identity(
    db: AsyncSession, user_id, source_event: str = "manual_refresh"
) -> EngineeringIdentityReport:
    """`source_event` — freshness fix: records WHY this snapshot exists,
    same pattern LeetcodeEngineeringSnapshot already uses. Callers that
    trigger this automatically after a real sync/upload event (see
    identity_refresh.py) pass the real event name; an explicit
    POST /identity/refresh keeps the "manual_refresh" default.
    """
    facts = await build_identity_facts(db, user_id)

    degraded = False
    try:
        print("[TRACING] Requesting Engineering Identity synthesis from LLM...", flush=True)
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": IDENTITY_SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(facts.model_dump(mode="json"))},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw Engineering Identity synthesis JSON:\n{content}", flush=True)
        narrative = IdentityLLMOutput.model_validate(json.loads(content))
    except Exception as e:
        print(f"[TRACING] Engineering Identity synthesis degraded, using fallback: {e}", flush=True)
        narrative = _fallback_narrative(facts)
        degraded = True

    report = EngineeringIdentityReport(
        facts=facts,
        narrative=narrative,
        generated_at=datetime.now(timezone.utc),
        analysis_degraded=degraded,
        source_event=source_event,
    )

    row = EngineeringIdentity(
        user_id=user_id,
        facts_json=facts.model_dump(mode="json"),
        narrative_json=narrative.model_dump(mode="json"),
        analysis_degraded=degraded,
        source_event=source_event,
        created_at=report.generated_at,
    )
    db.add(row)
    await db.flush()
    await db.commit()

    return report


async def get_latest_engineering_identity(db: AsyncSession, user_id) -> EngineeringIdentityReport | None:
    result = await db.execute(
        select(EngineeringIdentity)
        .where(EngineeringIdentity.user_id == user_id)
        .order_by(EngineeringIdentity.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return EngineeringIdentityReport(
        facts=IdentityFacts.model_validate(row.facts_json),
        narrative=IdentityLLMOutput.model_validate(row.narrative_json),
        generated_at=row.created_at,
        analysis_degraded=row.analysis_degraded,
        source_event=row.source_event,
    )