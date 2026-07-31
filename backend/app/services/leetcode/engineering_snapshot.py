"""Persistence + retrieval for the Engineering Maturity Quadrant and its
companion cross-module inferences (company readiness, resume-claim
check). Computation itself is fully deterministic (engineering_quadrant.py,
company_readiness.py, resume_claim_check.py) — this module only decides
WHEN to snapshot it and how to read history back, mirroring
github_analysis.py's PortfolioAnalysis pattern: append-only, tied to the
source LeetCode ProfileSnapshot for lineage, safe to recompute at any time.

Reads (get_latest_engineering_snapshot / get_engineering_snapshot_history)
never write. Writes only happen via persist_engineering_snapshot, called
explicitly by the API layer after a sync event that could plausibly move
the quadrant — never on a GET.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Resume
from app.models.inference import ProfileSnapshot
from app.models.leetcode_analysis import LeetcodeEngineeringSnapshot
from app.services.github.github_knowledge import build_github_knowledge_object
from app.services.leetcode.company_readiness import compute_company_readiness
from app.services.leetcode.engineering_quadrant import compute_engineering_quadrant
from app.services.leetcode.resume_claim_check import check_resume_claims


async def _get_latest_leetcode_profile_snapshot(db: AsyncSession, user_id) -> ProfileSnapshot | None:
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note.in_(["leetcode sync", "leetcode manual submission"]))
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_latest_resume_text(db: AsyncSession, user_id) -> str:
    result = await db.execute(
        select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(1)
    )
    resume = result.scalar_one_or_none()
    return resume.raw_text if resume else ""


async def compute_engineering_snapshot(db: AsyncSession, user_id) -> dict | None:
    """Fresh, read-only computation from the latest real LeetCode +
    GitHub + Resume data. Returns None if there's no LeetCode data yet
    at all — the quadrant is meaningless without at least one real
    LeetCode data point.
    """
    lc_snapshot = await _get_latest_leetcode_profile_snapshot(db, user_id)
    if lc_snapshot is None or not isinstance(lc_snapshot.skills_json, dict):
        return None

    insights = lc_snapshot.skills_json.get("insights", {})
    stats = lc_snapshot.skills_json.get("stats", {})
    topic_mastery = insights.get("topic_mastery", [])

    gh_knowledge = await build_github_knowledge_object(db, user_id)
    repositories = gh_knowledge.get("repositories", []) if gh_knowledge else []

    quadrant = compute_engineering_quadrant(topic_mastery, repositories)
    company_readiness = compute_company_readiness(topic_mastery)

    resume_text = await _get_latest_resume_text(db, user_id)
    resume_claims = check_resume_claims(
        resume_text,
        total_solved=stats.get("total_solved", 0),
        contest_rating=stats.get("contest_rating"),
        topic_mastery=topic_mastery,
    )

    return {
        "leetcode_snapshot_id": lc_snapshot.id,
        "leetcode_score": quadrant["leetcode_score"],
        "github_score": quadrant["github_score"],
        "quadrant_label": quadrant["quadrant_label"],
        "description": quadrant["description"],
        "company_readiness": company_readiness,
        "resume_claims": resume_claims,
    }


async def persist_engineering_snapshot(db: AsyncSession, user_id, source_event: str) -> LeetcodeEngineeringSnapshot | None:
    """Computes fresh and appends one row. Called explicitly by the API
    layer after any sync event that could move the quadrant (a LeetCode
    sync, a manual LeetCode submission, or a GitHub sync). Never
    overwrites or upserts a prior row — historical trend is the point.
    Returns None (no-op, no row written) if there's no LeetCode data yet.
    """
    computed = await compute_engineering_snapshot(db, user_id)
    if computed is None:
        return None

    row = LeetcodeEngineeringSnapshot(
        user_id=user_id,
        leetcode_snapshot_id=computed["leetcode_snapshot_id"],
        computed_at=datetime.now(timezone.utc),
        source_event=source_event,
        leetcode_score=computed["leetcode_score"],
        github_score=computed["github_score"],
        quadrant_label=computed["quadrant_label"],
        description=computed["description"],
        company_readiness=computed["company_readiness"],
        resume_claims=computed["resume_claims"],
    )
    db.add(row)
    await db.flush()
    await db.commit()
    return row


def _serialize(row: LeetcodeEngineeringSnapshot) -> dict:
    return {
        "computed_at": row.computed_at.isoformat(),
        "source_event": row.source_event,
        "leetcode_score": row.leetcode_score,
        "github_score": row.github_score,
        "quadrant_label": row.quadrant_label,
        "description": row.description,
        "company_readiness": row.company_readiness,
        "resume_claims": row.resume_claims,
    }


async def get_latest_engineering_snapshot(db: AsyncSession, user_id) -> dict | None:
    result = await db.execute(
        select(LeetcodeEngineeringSnapshot)
        .where(LeetcodeEngineeringSnapshot.user_id == user_id)
        .order_by(LeetcodeEngineeringSnapshot.computed_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return _serialize(row) if row else None


async def get_engineering_snapshot_history(db: AsyncSession, user_id, limit: int = 12) -> list[dict]:
    """Oldest-first, ready for direct trend rendering."""
    result = await db.execute(
        select(LeetcodeEngineeringSnapshot)
        .where(LeetcodeEngineeringSnapshot.user_id == user_id)
        .order_by(LeetcodeEngineeringSnapshot.computed_at.desc())
        .limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    return [_serialize(r) for r in rows]