# backend/app/services/identity/identity_context.py
"""Adapter between the persisted Engineering Identity layer and the
Interview Response Agent — the ONE place Interview reads from Identity
(implementation plan §3/§6). Never mutates anything; never triggers a
refresh (that's already wired into every real data-producing event via
identity_refresh.py — Interview is a pure consumer).

Falls back to a live, unpersisted build_identity_facts() computation
when the user has no EngineeringIdentity snapshot yet — same fallback
pattern api/sync.py's get_leetcode_workspace already uses for
engineering_quadrant.

Returns a SLIM projection for the "framing" layer only (top_skills here
is IdentityFacts' own top-10, role_fit, quadrant, etc.) — reusing
identity_synthesizer's own slimming helpers rather than re-deriving
them, so this can never disagree with what the synthesis LLM call
itself was given. This is NOT the source for context["profile"]["skills"]
— that field needs the full, unbounded reconciled skill list (every
evidenced skill, not just the top 10), which context_builder.py sources
directly from reconciled_confidence.get_reconciled_skill_confidences().
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.identity.identity_builder import build_identity_facts
from app.services.identity.identity_synthesizer import (
    _slim_coverage_gaps,
    _slim_top_skills,
    get_latest_engineering_identity,
)

MAX_COMPANY_READINESS_IN_CONTEXT = 3


async def build_identity_context_for_interview(db: AsyncSession, user_id) -> dict:
    """Slim Identity projection for the Interview Agent's prompt context.
    Shape:
    {
        "top_skills": [{"skill", "confidence", "corroboration_count", ...}],
        "role_fit": [{"role", "rating", "rationale"}],
        "engineering_quadrant": {...} | None,
        "company_readiness": [...],
        "claim_risk_details": [...],
        "coverage_gaps": {...slimmed...},
        "timeline_plausibility_notes": [...],
        "evidence_coverage": {...},
        "source_freshness": {...},
        "is_live_fallback": bool,  # true if no persisted snapshot existed yet
    }
    """
    cached = await get_latest_engineering_identity(db, user_id)

    if cached is not None:
        facts = cached.facts
        is_live_fallback = False
    else:
        facts = await build_identity_facts(db, user_id)
        is_live_fallback = True

    dumped = facts.model_dump(mode="json")

    return {
        "top_skills": _slim_top_skills(dumped.get("top_skills", [])),
        "role_fit": dumped.get("role_fit", []),
        "engineering_quadrant": dumped.get("engineering_quadrant"),
        "company_readiness": dumped.get("company_readiness", [])[:MAX_COMPANY_READINESS_IN_CONTEXT],
        "claim_risk_details": dumped.get("claim_risk_details", []),
        "coverage_gaps": _slim_coverage_gaps(dumped.get("coverage_gaps", {})),
        "timeline_plausibility_notes": dumped.get("timeline_plausibility_notes", []),
        "evidence_coverage": dumped.get("evidence_coverage", {}),
        "source_freshness": dumped.get("source_freshness", {}),
        "is_live_fallback": is_live_fallback,
    }