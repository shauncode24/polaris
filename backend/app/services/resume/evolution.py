"""Resume Evolution — diffs the two most recent "resume upload"
ProfileSnapshot rows for a user. Purely deterministic — no new LLM call,
no new storage.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inference import ProfileSnapshot
from app.schemas.resume.resume_evolution import EvolutionReport, SkillDelta

SIGNIFICANT_DELTA = 0.05


async def _get_recent_resume_snapshots(db: AsyncSession, user_id, limit: int = 2) -> list[ProfileSnapshot]:
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note == "resume upload")
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def _skills_map(snapshot: ProfileSnapshot) -> dict[str, float]:
    """Reads the FROZEN, upload-time confidence — deliberately diffed
    against the LIVE decayed number elsewhere in this file."""
    if not isinstance(snapshot.skills_json, dict):
        return {}
    return {
        canonical: data.get("confidence_at_upload", data.get("confidence", 0.0))
        for canonical, data in snapshot.skills_json.items()
        if isinstance(data, dict)
    }


async def build_evolution_report(db: AsyncSession, user_id) -> EvolutionReport:
    snapshots = await _get_recent_resume_snapshots(db, user_id, limit=2)

    if len(snapshots) < 2:
        return EvolutionReport(
            has_previous=False,
            current_snapshot_at=snapshots[0].taken_at if snapshots else None,
            summary="No previous resume upload to compare against yet.",
        )

    current, previous = snapshots[0], snapshots[1]

    # FIX (Critical): previously diffed a FROZEN confidence_at_upload for
    # `previous` against the LIVE, currently-decayed confidence for
    # `current` (via get_all_skill_confidences). That's an apples-to-
    # oranges comparison: if a user does nothing between two resume
    # uploads, pure time-decay on unrelated skills alone could show up
    # as "skill weakened since your last upload" with no real underlying
    # change — directly contradicting this module's stated purpose of
    # showing genuine change. Both sides must be measured at the same
    # kind of instant, so both now read the frozen confidence_at_upload
    # recorded on their own snapshot.
    current_skills = _skills_map(current)
    previous_skills = _skills_map(previous)

    gained = sorted(set(current_skills) - set(previous_skills))
    lost = sorted(set(previous_skills) - set(current_skills))

    strengthened: list[SkillDelta] = []
    weakened: list[SkillDelta] = []
    for skill in set(current_skills) & set(previous_skills):
        delta = round(current_skills[skill] - previous_skills[skill], 3)
        if delta >= SIGNIFICANT_DELTA:
            strengthened.append(SkillDelta(
                skill=skill, previous_confidence=previous_skills[skill],
                current_confidence=current_skills[skill], delta=delta,
            ))
        elif delta <= -SIGNIFICANT_DELTA:
            weakened.append(SkillDelta(
                skill=skill, previous_confidence=previous_skills[skill],
                current_confidence=current_skills[skill], delta=delta,
            ))

    strengthened.sort(key=lambda s: s.delta, reverse=True)
    weakened.sort(key=lambda s: s.delta)

    parts = []
    if gained:
        parts.append(f"gained evidence for {', '.join(gained[:5])}")
    if lost:
        parts.append(f"lost evidence for {', '.join(lost[:5])}")
    if strengthened:
        parts.append(f"strengthened {len(strengthened)} skill(s)")
    if weakened:
        parts.append(f"saw {len(weakened)} skill(s) weaken based on real evidence changes")
    summary = (
        "Since your last resume upload, you " + "; ".join(parts) + "."
        if parts else "No material skill changes detected since your last resume upload."
    )

    return EvolutionReport(
        has_previous=True,
        previous_snapshot_at=previous.taken_at,
        current_snapshot_at=current.taken_at,
        skills_gained=gained,
        skills_lost=lost,
        skills_strengthened=strengthened,
        skills_weakened=weakened,
        summary=summary,
    )