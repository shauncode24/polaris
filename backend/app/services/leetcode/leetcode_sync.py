# backend/app/services/leetcode/leetcode_sync.py
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import LeetcodeSnapshot
from app.models.inference import ProfileSnapshot, SkillEvidence
from app.services.resume.confidence import WEIGHTS
from app.services.leetcode.leetcode_client import LeetCodeSyncError, fetch_leetcode_profile
from app.services.leetcode.leetcode_insights import build_leetcode_insights
from app.services.resume.skill_classifier import resolve_skills
from app.services.user_helpers import get_or_create_skill


async def _get_previous_tag_counts(db: AsyncSession, user_id) -> dict[str, int]:
    result = await db.execute(
        select(LeetcodeSnapshot.tag, LeetcodeSnapshot.solved_count, LeetcodeSnapshot.pulled_at)
        .where(LeetcodeSnapshot.user_id == user_id)
        .order_by(LeetcodeSnapshot.tag, LeetcodeSnapshot.pulled_at.desc())
    )
    latest: dict[str, int] = {}
    for tag, solved_count, _pulled_at in result.all():
        if tag not in latest:
            latest[tag] = solved_count
    return latest


async def _get_existing_evidence_skill_ids(db: AsyncSession) -> set:
    result = await db.execute(
        select(SkillEvidence.skill_id).where(SkillEvidence.source_type == "leetcode_tag")
    )
    return {row[0] for row in result.all()}


async def _get_previous_leetcode_stats(db: AsyncSession, user_id) -> dict | None:
    """Pulls total_solved / contest_rating from the last LeetCode sync's
    ProfileSnapshot so build_progress() has a baseline to diff against —
    same idea as github_sync.py's prev_insights lookup.
    """
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note.in_(["leetcode sync", "leetcode manual submission"]))
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    prev = result.scalar_one_or_none()
    if prev and isinstance(prev.skills_json, dict):
        return prev.skills_json.get("stats")
    return None


async def _persist_leetcode_data(
    db: AsyncSession,
    user,
    tag_counts: dict[str, int],
    note: str,
    extra_stats: dict | None = None,
) -> dict:
    previous_tag_counts = await _get_previous_tag_counts(db, user.id)
    existing_evidence_skill_ids = await _get_existing_evidence_skill_ids(db)
    previous_stats = await _get_previous_leetcode_stats(db, user.id)

    for tag, count in tag_counts.items():
        db.add(
            LeetcodeSnapshot(
                user_id=user.id, pulled_at=datetime.now(timezone.utc),
                tag=tag, solved_count=count, difficulty=None,
            )
        )

    resolved = await resolve_skills(set(tag_counts.keys()), db)

    tags_report: list[dict] = []
    reinforced_skills: list[str] = []
    new_skills: list[str] = []
    unchanged_skills: list[str] = []

    for tag, count in tag_counts.items():
        canonical = resolved.get(tag)
        skill_updated = False

        if canonical is not None:
            skill = await get_or_create_skill(db, canonical, tag)
            prev_count = previous_tag_counts.get(tag)

            if skill.id not in existing_evidence_skill_ids:
                db.add(SkillEvidence(
                    skill_id=skill.id, source_type="leetcode_tag",
                    source_id=None, weight=WEIGHTS["leetcode_tag"],
                ))
                existing_evidence_skill_ids.add(skill.id)
                new_skills.append(canonical)
                skill_updated = True
            elif prev_count is not None and count > prev_count:
                reinforced_skills.append(canonical)
                skill_updated = True
            else:
                unchanged_skills.append(canonical)

        tags_report.append({"tag": tag, "solved": count, "skill_updated": skill_updated})

    await db.flush()

    insights = build_leetcode_insights(
        tag_counts=tag_counts,
        previous_tag_counts=previous_tag_counts or None,
        total_solved=(extra_stats or {}).get("total_solved", sum(tag_counts.values())),
        previous_total_solved=(previous_stats or {}).get("total_solved"),
        easy=(extra_stats or {}).get("easy", 0),
        previous_easy=(previous_stats or {}).get("easy"),
        medium=(extra_stats or {}).get("medium", 0),
        previous_medium=(previous_stats or {}).get("medium"),
        hard=(extra_stats or {}).get("hard", 0),
        previous_hard=(previous_stats or {}).get("hard"),
        attended_contests_count=(extra_stats or {}).get("attended_contests_count", 0),
        active_days_last_30=(extra_stats or {}).get("active_days_last_30", 0),
        submissions_last_30=(extra_stats or {}).get("submissions_last_30", 0),
        longest_gap_days=(extra_stats or {}).get("longest_gap_days", 0),
        reinforced_skills=reinforced_skills,
        new_skills=new_skills,
        unchanged_skills=unchanged_skills,
    )

    snapshot_skills_json = {"leetcode_tags_synced": list(tag_counts.keys()), "insights": insights}
    if extra_stats:
        snapshot_skills_json["stats"] = extra_stats

    snapshot = ProfileSnapshot(
        user_id=user.id, taken_at=datetime.now(timezone.utc),
        skills_json=snapshot_skills_json, note=note,
    )
    db.add(snapshot)
    await db.flush()
    await db.commit()

    return {
        "status": "success",
        "synced_at": snapshot.taken_at.isoformat(),
        "user_id": str(user.id),
        "snapshot_id": str(snapshot.id),
        "summary": {k: (extra_stats or {}).get(k) for k in (
            "total_solved", "easy", "medium", "hard", "contest_rating",
            "global_ranking", "attended_contests_count", "active_days_last_30",
            "longest_streak", "current_streak", "longest_gap_days",
        )},
        "tags": tags_report,
        "skill_evidence": {
            "created": len(new_skills), "updated": len(reinforced_skills), "unchanged": len(unchanged_skills),
        },
        "insights": insights,
        "profile_snapshot_created": True,
    }


async def sync_leetcode(db: AsyncSession, user, username: str) -> dict:
    print(f"[TRACING] Starting LeetCode sync for {username}...", flush=True)
    profile = await fetch_leetcode_profile(username)
    print(f"[TRACING] LeetCode sync fetched {len(profile['tag_counts'])} tags.", flush=True)
    extra_stats = {k: v for k, v in profile.items() if k != "tag_counts"}
    result = await _persist_leetcode_data(db, user, profile["tag_counts"], note="leetcode sync", extra_stats=extra_stats)
    print("[TRACING] LeetCode sync complete.", flush=True)
    return result


async def sync_leetcode_manual(db: AsyncSession, user, tag_counts: dict[str, int]) -> dict:
    print(f"[TRACING] Persisting manual LeetCode submission ({len(tag_counts)} tags)...", flush=True)
    result = await _persist_leetcode_data(db, user, tag_counts, note="leetcode manual submission")
    print("[TRACING] Manual LeetCode submission persisted.", flush=True)
    return result