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
    NarrativeClaim,
)
from app.services.identity.identity_builder import build_identity_facts
from app.services.projects.linking import normalize_name


class IdentitySynthesisError(Exception):
    """Raised when the synthesis LLM call fails or returns something we
    can't validate. Callers fall back to a deterministic template
    instead of crashing the whole report.
    """


# ---------------------------------------------------------------------
# LLM payload slimming
#
# IdentityFacts (the full object, with real per-source labels — project
# names, repo names, experience labels) remains the single source of
# truth: it's what gets persisted, returned from the API, and read by
# the fallback narrative builder below. The functions in this section
# build a SEPARATE, reduced projection of that object used ONLY for the
# JSON actually sent to the synthesis LLM call.
#
# The redundancy this removes: `top_skills[].sources` and
# `coverage_gaps.*.repos`/`.certs` were repeating the same project/repo
# names dozens of times across a profile with many synced repos (e.g.
# "javascript" evidenced in 22 repos, then the same 21 repo names again
# under coverage_gaps, then again under a different skill's sources).
# The prompt never cites these names — it reasons over `confidence` and
# `corroboration_count`, which are kept untouched. `role_fit_evidence_hash`
# is dropped entirely; it's cache-key plumbing for identity_builder.py,
# never referenced by the prompt. `technology_depth_highlights[].breakdown`
# is dropped too — the prompt only ever cites `score`/`label`.
#
# This is what fixed the 413 (Request Entity Too Large) from Groq: the
# token *estimate* looked fine (~4k), but the raw serialized JSON bytes —
# inflated by repeated evidence strings — were what actually tripped the
# request-size ceiling.
# ---------------------------------------------------------------------

def _summarize_sources(sources: list[str]) -> dict:
    """Collapses a per-skill evidence source list ("Project: Campus
    Intel", "GitHub: Attendance-Tracker", ...) into counts by source
    type, instead of sending every individual label. Deduplicates
    near-identical labels first (e.g. "Project: Campus Intel" and
    "Project: Project 1: Campus Intel" refer to the same underlying
    project — a side effect of resume re-uploads creating duplicate
    Project rows) using the same normalize_name() the Projects module
    already uses for exactly this kind of dedup.
    """
    deduped: set[tuple[str, str]] = set()
    type_counts: dict[str, int] = {}
    for s in sources:
        prefix, _, rest = s.partition(":")
        prefix = prefix.strip()
        key = normalize_name(rest) if rest.strip() else s
        dedup_key = (prefix, key)
        if dedup_key in deduped:
            continue
        deduped.add(dedup_key)
        type_counts[prefix] = type_counts.get(prefix, 0) + 1
    return {"source_count": len(deduped), "source_types": type_counts}


def _slim_top_skills(top_skills: list[dict]) -> list[dict]:
    slimmed = []
    for s in top_skills:
        entry = {
            "skill": s["skill"],
            "confidence": s["confidence"],
            "corroboration_count": s.get("corroboration_count", 0),
        }
        # Only include raw_confidence/confidence_flags when a real
        # discount was actually applied — omitting them when there's
        # nothing to explain is itself a size saving across a profile
        # where most skills have no flags.
        if s.get("confidence_flags"):
            entry["raw_confidence"] = s.get("raw_confidence", entry["confidence"])
            entry["confidence_flags"] = s["confidence_flags"]
        entry.update(_summarize_sources(s.get("sources", [])))
        slimmed.append(entry)
    return slimmed


def _slim_technology_depth(highlights: list[dict]) -> list[dict]:
    return [
        {
            "technology": h.get("technology"),
            "score": h.get("score"),
            "label": h.get("label"),
            "repo_count": h.get("repo_count"),
        }
        for h in highlights
    ]


def _slim_coverage_gaps(coverage_gaps: dict) -> dict:
    """github_gaps/certificate_gaps each repeat a "repos"/"certs" name
    list that's already summarized in that same entry's "reason" text
    (e.g. "Evidenced in your GitHub repo 'api-beginner, ...'") — the
    raw array is redundant with the sentence right next to it. Replaced
    with a count. leetcode_gaps and project_suggestions carry no such
    per-entry name lists and are left untouched.
    """
    slimmed = dict(coverage_gaps)

    github_gaps = slimmed.get("github_gaps")
    if github_gaps:
        slimmed["github_gaps"] = [
            {"skill": g.get("skill"), "reason": g.get("reason"), "repo_count": len(g.get("repos", []))}
            for g in github_gaps
        ]

    certificate_gaps = slimmed.get("certificate_gaps")
    if certificate_gaps:
        slimmed["certificate_gaps"] = [
            {"skill": g.get("skill"), "reason": g.get("reason"), "cert_count": len(g.get("certs", []))}
            for g in certificate_gaps
        ]

    return slimmed


def _build_synthesis_payload(facts: IdentityFacts) -> dict:
    """The JSON actually sent to the synthesis LLM call — a reduced
    projection of IdentityFacts, never a substitute for it. See the
    module-level comment above for what's cut and why.
    """
    dumped = facts.model_dump(mode="json")
    dumped.pop("role_fit_evidence_hash", None)
    dumped["top_skills"] = _slim_top_skills(dumped.get("top_skills", []))
    dumped["technology_depth_highlights"] = _slim_technology_depth(
        dumped.get("technology_depth_highlights", [])
    )
    dumped["coverage_gaps"] = _slim_coverage_gaps(dumped.get("coverage_gaps", {}))
    return dumped


def _fact_claim(statement: str, grounded_in: str) -> NarrativeClaim:
    return NarrativeClaim(statement=statement, kind="fact", grounded_in=grounded_in)


def _fallback_freshness_note(facts: IdentityFacts) -> str:
    stale_or_missing = [
        source for source, info in facts.source_freshness.items()
        if not info.get("connected") or info.get("is_stale")
    ]
    if not stale_or_missing:
        return "All connected sources are fresh." if facts.source_freshness else ""

    parts = []
    for source in stale_or_missing:
        info = facts.source_freshness[source]
        if not info.get("connected"):
            parts.append(f"{source} has never been connected")
        else:
            parts.append(f"{source} data is {info.get('age_days')} days old")
    return "Note: " + "; ".join(parts) + "."


def _fallback_narrative(facts: IdentityFacts) -> IdentityLLMOutput:
    top_names = [s.skill.title() for s in facts.top_skills[:4]]
    best_role = facts.role_fit[0] if facts.role_fit else None

    summary_parts = []
    if best_role:
        summary_parts.append(
            f"Your strongest evidenced fit is {best_role.role} (rated {best_role.rating}/5)."
        )
    if top_names:
        summary_parts.append(f"Your most-evidenced skills are {', '.join(top_names)}.")
    if facts.resume_score is not None:
        summary_parts.append(f"Resume score is currently {facts.resume_score}/100.")
    if facts.engineering_quadrant:
        summary_parts.append(f"Engineering placement: {facts.engineering_quadrant['quadrant_label']}.")
    if facts.evidence_coverage:
        summary_parts.append(
            f"Evidence coverage: {facts.evidence_coverage.get('completeness_label', 'unknown').lower()}."
        )

    strongest_signals = [
        _fact_claim(
            f"{s.skill.title()} — confidence {s.confidence}, corroborated by {s.corroboration_count} independent source(s).",
            f"top_skills: {s.skill} (confidence {s.confidence}, corroboration_count={s.corroboration_count})",
        )
        for s in facts.top_skills[:4]
    ]

    gaps: list[NarrativeClaim] = []
    if facts.coverage_gaps.get("github_gaps"):
        gaps.append(_fact_claim(
            f"{len(facts.coverage_gaps['github_gaps'])} GitHub-evidenced skill(s) missing from your resume.",
            "coverage_gaps.github_gaps",
        ))
    if facts.timeline_plausibility_notes:
        gaps.append(_fact_claim(
            f"{len(facts.timeline_plausibility_notes)} timeline note(s) worth reviewing.",
            "timeline_plausibility_notes",
        ))
    if facts.claim_risk_details:
        gaps.append(_fact_claim(
            f"{len(facts.claim_risk_details)} project(s) with unresolved claim-vs-implementation risk.",
            "claim_risk_details",
        ))
    if facts.evidence_coverage.get("missing_sources", 0) > 0:
        gaps.append(_fact_claim(
            f"{facts.evidence_coverage['missing_sources']} evidence source(s) have never been connected.",
            "evidence_coverage.missing_sources",
        ))
    if facts.portfolio_narrative and not facts.portfolio_narrative.analysis_degraded:
        gaps.append(_fact_claim(
            f"Portfolio weakness: {facts.portfolio_narrative.biggest_weakness}",
            "portfolio_narrative.biggest_weakness",
        ))

    return IdentityLLMOutput(
        headline=best_role.role if best_role else "Engineering profile",
        summary=" ".join(summary_parts) or "Not enough evidence yet to summarize your profile.",
        strongest_signals=strongest_signals,
        biggest_gaps=gaps,
        contradictions=[
            f"{c['project']}: {c['headline']}" for c in facts.claim_risk_details[:2]
        ],
        recommended_focus=(
            "Sync GitHub and LeetCode, then re-run this once more evidence exists."
            if not top_names else ""
        ),
        freshness_note=_fallback_freshness_note(facts),
    )


def _validate_claims(claims: list[NarrativeClaim]) -> list[NarrativeClaim]:
    """Never trust the model's own "kind" labeling blindly — same
    defensive pattern applied everywhere else in this codebase (e.g.
    claim_audit's risk_level being overwritten with the deterministic
    fact, gap_analysis filtering priority_order to real skill names). A
    claim tagged "fact" with no real citation is, by definition, not
    grounded — downgrade it to "interpretation" rather than let an
    ungrounded "fact" label reach the user.
    """
    validated = []
    for claim in claims:
        if claim.kind == "fact" and not claim.grounded_in.strip():
            claim = NarrativeClaim(statement=claim.statement, kind="interpretation", grounded_in="")
        validated.append(claim)
    return validated


def _row_to_report(row: EngineeringIdentity) -> EngineeringIdentityReport:
    return EngineeringIdentityReport(
        facts=IdentityFacts.model_validate(row.facts_json),
        narrative=IdentityLLMOutput.model_validate(row.narrative_json),
        generated_at=row.created_at,
        analysis_degraded=row.analysis_degraded,
        source_event=row.source_event,
        is_invalidated=row.is_invalidated,
        invalidated_reason=row.invalidated_reason,
        invalidated_at=row.invalidated_at,
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
        llm_payload = _build_synthesis_payload(facts)
        print(f"[TRACING] LLM payload JSON:\n{llm_payload}", flush=True)
        print(
            f"[TRACING] Requesting Engineering Identity synthesis from LLM "
            f"(payload ~{len(json.dumps(llm_payload))} chars, "
            f"full facts ~{len(json.dumps(facts.model_dump(mode='json')))} chars)...",
            flush=True,
        )
        response = await chat_completion(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": IDENTITY_SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(llm_payload)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw Engineering Identity synthesis JSON:\n{content}", flush=True)
        narrative = IdentityLLMOutput.model_validate(json.loads(content))
        narrative.strongest_signals = _validate_claims(narrative.strongest_signals)
        narrative.biggest_gaps = _validate_claims(narrative.biggest_gaps)
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
    """Returns the most recent VALID (non-invalidated) snapshot. An
    invalidated row is skipped entirely rather than returned with a
    warning flag — a consumer asking "what's my current Identity"
    should never be handed something already known to be wrong; that
    row is only reachable via get_engineering_identity_history() or by
    id, for someone specifically investigating past behavior.
    """
    result = await db.execute(
        select(EngineeringIdentity)
        .where(EngineeringIdentity.user_id == user_id)
        .where(EngineeringIdentity.is_invalidated.is_(False))
        .order_by(EngineeringIdentity.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return _row_to_report(row) if row else None


async def get_engineering_identity_history(
    db: AsyncSession, user_id, limit: int = 10
) -> list[EngineeringIdentityReport]:
    """Most-recent-first, INCLUDING invalidated rows (with their
    is_invalidated/invalidated_reason/invalidated_at set) — this is the
    one place a consumer can actually see "why did Identity say X three
    days ago" and whether that snapshot was later flagged as wrong.
    """
    result = await db.execute(
        select(EngineeringIdentity)
        .where(EngineeringIdentity.user_id == user_id)
        .order_by(EngineeringIdentity.created_at.desc())
        .limit(limit)
    )
    return [_row_to_report(row) for row in result.scalars().all()]


async def invalidate_engineering_identity(
    db: AsyncSession, user_id, identity_id, reason: str
) -> EngineeringIdentityReport | None:
    """Flags one specific past row as known-bad — audit finding #3. Does
    NOT delete or rewrite the row (append-only history stays intact for
    Weekly Brief's diffing), and does NOT trigger a new generation —
    callers that also want a fresh, corrected snapshot should follow
    this with their own POST /identity/refresh.
    """
    result = await db.execute(
        select(EngineeringIdentity)
        .where(EngineeringIdentity.id == identity_id)
        .where(EngineeringIdentity.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    row.is_invalidated = True
    row.invalidated_reason = reason
    row.invalidated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return _row_to_report(row)