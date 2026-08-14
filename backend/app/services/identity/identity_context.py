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

TOKEN BUDGET FIX: this is now where the interview-specific slimming
lives, on top of identity_synthesizer's own general-purpose slimming
(_slim_top_skills / _slim_coverage_gaps). Two real problems were making
the interview payload oversized:

  1. claim_risk_details could contain duplicate entries for the same
     conceptual project — a known consequence of duplicate Project rows
     from repeated resume uploads (see projects/overview.py's own
     normalize_name-based dedup for the same underlying issue). Each
     duplicate Project row gets its own Claim Audit row, so the same
     real finding could appear twice, or more, in the raw facts.
  2. source_freshness and coverage_gaps.project_suggestions are real,
     useful fields — but the INTERVIEW prompt never references either
     one (only identity.evidence_coverage.completeness_label is used
     for freshness calibration; project_suggestions is a Resume-
     workspace-facing field). Sending fields a prompt never reads is
     pure token waste.

Neither of these is new "smart" filtering — it's dropping duplicates and
fields with no consumer in this specific prompt, the same way
identity_synthesizer.py already slims for its own (different) prompt.

WEAKNESS-SIGNAL FIX (Interview Agent implementation plan §E): before
this existed, only "strengths" had a deterministic signal to draw on
(identity.top_skills) — a weakness-shaped question (biggest_weakness,
failure, mistake) had nothing equivalent, so the plan stage had to
either invent a generic weakness or reach vaguely into coverage_gaps
text. "weakness_signals" fixes that: it surfaces real, LOW-confidence
but genuinely EVIDENCED skills (the candidate has real, if thin,
evidence — this is never an invented gap) plus real cross-source gap
counts, computed fresh from the SAME unbounded reconciled-confidence
map the Skill Gap Analyzer uses, not from the top-10-only top_skills
slice (a weak skill will almost never make that top-10 cut by
definition).

Returns a SLIM projection for the "framing" layer only (top_skills here
is IdentityFacts' own top-10, role_fit, quadrant, etc.) — reusing
identity_synthesizer's own slimming helpers rather than re-deriving
them, so this can never disagree with what the synthesis LLM call
itself was given. This is NOT the source for context["profile"]["skills"]
— that field needs the full, unbounded reconciled skill list (every
evidenced skill, not just the top 10), which context_builder.py sources
directly from reconciled_confidence.get_reconciled_skill_confidences()
(itself slimmed to skill+confidence only — see that module's docstring).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.identity.identity_builder import build_identity_facts
from app.services.identity.identity_synthesizer import (
    _slim_coverage_gaps,
    _slim_top_skills,
    get_latest_engineering_identity,
)
from app.services.identity.reconciled_confidence import get_reconciled_skill_confidences
from app.services.projects.linking import normalize_name
from app.services.resume.confidence_thresholds import medium_floor

MAX_COMPANY_READINESS_IN_CONTEXT = 3
# Each remaining coverage_gaps list (github_gaps/leetcode_gaps/
# certificate_gaps) capped to this many entries — the interview prompt
# only ever uses coverage_gaps DIRECTIONALLY ("more reason to be
# conservative about implying strength here"), never to cite a specific
# gap by name, so the full list adds size without adding usable signal.
MAX_COVERAGE_GAP_ITEMS = 6
# How many low-confidence evidenced skills to surface for weakness-
# shaped questions — small on purpose, this is meant to hand the plan
# stage a short, specific shortlist to choose ONE real thing from, not
# a comprehensive gap report.
MAX_WEAKNESS_SKILLS = 5


def _dedupe_claim_risk_details(details: list[dict]) -> list[dict]:
    """Keeps the first occurrence per normalized project name. Uses the
    exact same normalize_name() the Projects module already uses for
    duplicate-project dedup elsewhere (overview.py, linking.py), so this
    can't disagree with how "the same project" is defined anywhere else
    in the codebase.
    """
    seen: set[str] = set()
    deduped: list[dict] = []
    for entry in details:
        key = normalize_name(entry.get("project") or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _slim_coverage_gaps_for_interview(coverage_gaps: dict) -> dict:
    """Interview-specific trim, layered on top of identity_synthesizer's
    own _slim_coverage_gaps (which already replaces raw repo/cert name
    lists with counts). Drops project_suggestions entirely — a Resume-
    workspace-facing field the interview prompt never reads — and caps
    the remaining gap lists.
    """
    slimmed = _slim_coverage_gaps(coverage_gaps)
    slimmed.pop("project_suggestions", None)
    for key in ("github_gaps", "leetcode_gaps", "certificate_gaps"):
        if slimmed.get(key):
            slimmed[key] = slimmed[key][:MAX_COVERAGE_GAP_ITEMS]
    return slimmed


async def _build_weakness_signals(db: AsyncSession, user_id, raw_coverage_gaps: dict) -> dict:
    """Real, low-confidence-but-evidenced skills the candidate can
    honestly talk about as a weakness, plus real cross-source gap
    counts — see module docstring. Computed from the SAME unbounded,
    already-reconciled (claim-risk/timeline discounted) confidence map
    reconciled_confidence.get_reconciled_skill_confidences() produces
    for the Skill Gap Analyzer, so a skill surfaced here can never
    disagree with what GET /identity or GET /jobs/{id} would say about
    that same skill's confidence.

    "low_confidence_evidenced_skills" only ever contains skills with
    REAL evidence rows (this function reads from the reconciled map,
    which by construction only includes skills that have evidence at
    all) — this is deliberately distinct from an unevidenced/"missing"
    skill, which isn't honest material for a real interview story about
    a real weakness.
    """
    reconciled = await get_reconciled_skill_confidences(db, user_id)
    floor = medium_floor()
    weak_entries = sorted(
        (e for e in reconciled.values() if e["confidence"] < floor),
        key=lambda e: e["confidence"],
    )[:MAX_WEAKNESS_SKILLS]

    return {
        "low_confidence_evidenced_skills": [
            {"skill": e["skill"], "confidence": e["confidence"]} for e in weak_entries
        ],
        "github_gap_count": len(raw_coverage_gaps.get("github_gaps") or []),
        "leetcode_gap_count": len(raw_coverage_gaps.get("leetcode_gaps") or []),
        "certificate_gap_count": len(raw_coverage_gaps.get("certificate_gaps") or []),
    }


async def build_identity_context_for_interview(db: AsyncSession, user_id) -> dict:
    """Slim Identity projection for the Interview Agent's prompt context.
    Shape:
    {
        "top_skills": [{"skill", "confidence", "corroboration_count", ...}],
        "role_fit": [{"role", "rating", "rationale"}],
        "engineering_quadrant": {...} | None,
        "company_readiness": [...],
        "claim_risk_details": [...],       # deduped by project name
        "coverage_gaps": {...slimmed, project_suggestions dropped...},
        "weakness_signals": {...},          # NEW — see module docstring
        "timeline_plausibility_notes": [...],
        "evidence_coverage": {...},
        "is_live_fallback": bool,  # true if no persisted snapshot existed yet
    }
    Deliberately does NOT include "source_freshness" — the raw per-source
    freshness dict is real data, but nothing in the interview prompt
    reads it (only evidence_coverage.completeness_label is referenced),
    so it's dropped here rather than shipped unused.
    """
    cached = await get_latest_engineering_identity(db, user_id)

    if cached is not None:
        facts = cached.facts
        is_live_fallback = False
    else:
        facts = await build_identity_facts(db, user_id)
        is_live_fallback = True

    dumped = facts.model_dump(mode="json")
    raw_coverage_gaps = dumped.get("coverage_gaps", {})

    return {
        "top_skills": _slim_top_skills(dumped.get("top_skills", [])),
        "role_fit": dumped.get("role_fit", []),
        "engineering_quadrant": dumped.get("engineering_quadrant"),
        "company_readiness": dumped.get("company_readiness", [])[:MAX_COMPANY_READINESS_IN_CONTEXT],
        "claim_risk_details": _dedupe_claim_risk_details(dumped.get("claim_risk_details", [])),
        "coverage_gaps": _slim_coverage_gaps_for_interview(raw_coverage_gaps),
        "weakness_signals": await _build_weakness_signals(db, user_id, raw_coverage_gaps),
        "timeline_plausibility_notes": dumped.get("timeline_plausibility_notes", []),
        "evidence_coverage": dumped.get("evidence_coverage", {}),
        "is_live_fallback": is_live_fallback,
    }