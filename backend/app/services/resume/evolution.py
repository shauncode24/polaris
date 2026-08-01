"""Resume Evolution — diffs the two most recent "resume upload"
ProfileSnapshot rows for a user. Purely deterministic — no new LLM call,
no new storage. ingestion.py already writes a ProfileSnapshot on every
upload (see its skills_json); this was just never read back as a diff.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inference import ProfileSnapshot
from app.schemas.resume_evolution import EvolutionReport, SkillDelta
from app.services.evidence import get_all_skill_confidences

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
    """Reads the FROZEN, upload-time confidence — deliberately (per this
    module's own original design) diffed against the LIVE decayed number
    elsewhere in this file. Key renamed to confidence_at_upload (fix #10)
    so this distinction is enforced by the schema, not by a comment."""
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
    current_skills = await get_all_skill_confidences(db)
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