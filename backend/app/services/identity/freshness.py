"""Deterministic cross-source recency + evidence-completeness signals for
Engineering Identity — Audit findings #1 and #2.

Every source Identity blends together (resume, GitHub, LeetCode, Claim
Audits, job-description analyses) is fetched independently, on its own
schedule, by whichever page the user last visited. Before this module
existed, build_identity_facts() silently treated all of that as one
simultaneous "now" — nothing recorded how old each piece was, and
nothing distinguished "this source has never been connected" from "this
source was connected but its data just happens to have nothing to say
right now" (both rendered as empty/default fields, indistinguishable to
a consumer).

This module computes two things, both purely from timestamps/booleans
already sitting in the database — no LLM, no new evidence gathered:

1. source_freshness — per-source "as_of" timestamp + age_days + a
   deterministic is_stale flag, so the synthesis LLM can reason about
   staleness explicitly instead of it being invisible.
2. evidence_coverage — which sources are connected at all, how many are
   stale/missing, and a coarse completeness label — so any consumer can
   calibrate trust in the object before reading its narrative.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import JobDescription, Project, Resume
from app.models.inference import ProfileSnapshot, ProjectClaimAuditReview

# (source_key -> staleness_ceiling_days) — past this many days since the
# most recent real data point, a source is flagged stale. Hand-set and
# explainable, same philosophy as resume/decay.py's DECAY_STEPS: a
# resume is expected to change rarely (a longer window is fine), while
# GitHub/LeetCode activity is expected to move week to week for an
# actively-practicing candidate.
STALENESS_CEILING_DAYS: dict[str, int] = {
    "resume": 45,
    "github": 14,
    "leetcode": 14,
    "claim_audit": 30,
    "job_descriptions": 30,
}

ALL_SOURCES = list(STALENESS_CEILING_DAYS.keys())


def _age_days(taken_at: datetime | None) -> int | None:
    if taken_at is None:
        return None
    if taken_at.tzinfo is None:
        taken_at = taken_at.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - taken_at).days)


async def _latest_resume_at(db: AsyncSession, user_id) -> datetime | None:
    result = await db.execute(
        select(Resume.created_at)
        .where(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_github_sync_at(db: AsyncSession, user_id) -> datetime | None:
    result = await db.execute(
        select(ProfileSnapshot.taken_at)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note == "github sync")
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_leetcode_sync_at(db: AsyncSession, user_id) -> datetime | None:
    result = await db.execute(
        select(ProfileSnapshot.taken_at)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note.in_(["leetcode sync", "leetcode manual submission"]))
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_claim_audit_at(db: AsyncSession, user_id) -> datetime | None:
    proj_result = await db.execute(select(Project.id).where(Project.user_id == user_id))
    project_ids = [r[0] for r in proj_result.all()]
    if not project_ids:
        return None
    result = await db.execute(
        select(ProjectClaimAuditReview.created_at)
        .where(ProjectClaimAuditReview.project_id.in_(project_ids))
        .order_by(ProjectClaimAuditReview.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_job_description_at(db: AsyncSession, user_id) -> datetime | None:
    result = await db.execute(
        select(JobDescription.created_at)
        .where(JobDescription.user_id == user_id)
        .where(JobDescription.analysis_result.isnot(None))
        .order_by(JobDescription.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


_FETCHERS = {
    "resume": _latest_resume_at,
    "github": _latest_github_sync_at,
    "leetcode": _latest_leetcode_sync_at,
    "claim_audit": _latest_claim_audit_at,
    "job_descriptions": _latest_job_description_at,
}


async def compute_source_freshness(db: AsyncSession, user_id) -> dict[str, dict]:
    """{source_key: {"as_of": iso str | None, "age_days": int | None,
    "is_stale": bool, "connected": bool}}. "connected" is true the
    moment ANY real data point for that source has ever existed —
    staleness is a separate, orthogonal question from whether the
    source has ever been used at all (audit finding #2).
    """
    out: dict[str, dict] = {}
    for source, fetcher in _FETCHERS.items():
        taken_at = await fetcher(db, user_id)
        age_days = _age_days(taken_at)
        ceiling = STALENESS_CEILING_DAYS[source]
        out[source] = {
            "as_of": taken_at.isoformat() if taken_at else None,
            "age_days": age_days,
            "is_stale": age_days is not None and age_days > ceiling,
            "connected": taken_at is not None,
        }
    return out


_COMPLETENESS_LABELS: list[tuple[float, str]] = [
    (0.9, "Comprehensive — most sources connected and fresh"),
    (0.6, "Partial — some sources missing or stale"),
    (0.3, "Thin — built from limited evidence"),
    (0.0, "Minimal — almost no connected evidence"),
]


def compute_evidence_coverage(source_freshness: dict[str, dict]) -> dict:
    """Coarse, deterministic completeness signal derived purely from
    source_freshness — never re-fetches anything. A source counts as
    "fully contributing" only if it's BOTH connected and not stale;
    connected-but-stale counts as half credit, since stale evidence is
    still real evidence, just aging, not the same as never having
    existed at all.
    """
    total = len(source_freshness)
    connected = sum(1 for s in source_freshness.values() if s["connected"])
    stale = sum(1 for s in source_freshness.values() if s["connected"] and s["is_stale"])
    missing = total - connected

    fresh_connected = connected - stale
    completeness_score = (fresh_connected + stale * 0.5) / total if total else 0.0

    label = _COMPLETENESS_LABELS[-1][1]
    for floor, candidate_label in _COMPLETENESS_LABELS:
        if completeness_score >= floor:
            label = candidate_label
            break

    return {
        "total_sources": total,
        "connected_sources": connected,
        "stale_sources": stale,
        "missing_sources": missing,
        "completeness_score": round(completeness_score, 2),
        "completeness_label": label,
    }