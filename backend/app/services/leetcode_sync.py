from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import LeetcodeSnapshot
from app.models.inference import ProfileSnapshot, SkillEvidence
from app.services.confidence import WEIGHTS
from app.services.leetcode_client import LeetCodeSyncError, fetch_leetcode_profile
from app.services.skill_classifier import resolve_skills
from app.services.user_helpers import get_or_create_default_user, get_or_create_skill


async def _get_previous_tag_counts(db: AsyncSession, user_id) -> dict[str, int]:
    """Most recent solved_count per tag from prior syncs, so we can tell
    whether a tag's evidence is new, has grown, or is unchanged since the
    last sync — instead of just re-reporting the current state blind.
    """
    result = await db.execute(
        select(LeetcodeSnapshot.tag, LeetcodeSnapshot.solved_count, LeetcodeSnapshot.pulled_at)
        .where(LeetcodeSnapshot.user_id == user_id)
        .order_by(LeetcodeSnapshot.tag, LeetcodeSnapshot.pulled_at.desc())
    )
    latest: dict[str, int] = {}
    for tag, solved_count, _pulled_at in result.all():
        if tag not in latest:  # first row per tag = most recent, thanks to ORDER BY
            latest[tag] = solved_count
    return latest


async def _get_existing_evidence_skill_ids(db: AsyncSession) -> set:
    """Skills that already have leetcode_tag evidence from a prior sync.
    Prevents re-syncing an unchanged tag from silently inserting a
    duplicate SkillEvidence row and inflating confidence for no reason —
    keeps inference honestly re-derivable from facts (design doc §5.5).
    """
    result = await db.execute(
        select(SkillEvidence.skill_id).where(SkillEvidence.source_type == "leetcode_tag")
    )
    return {row[0] for row in result.all()}


async def _persist_leetcode_data(
    db: AsyncSession,
    tag_counts: dict[str, int],
    note: str,
    extra_stats: dict | None = None,
) -> dict:
    user = await get_or_create_default_user(db)

    previous_tag_counts = await _get_previous_tag_counts(db, user.id)
    existing_evidence_skill_ids = await _get_existing_evidence_skill_ids(db)

    for tag, count in tag_counts.items():
        db.add(
            LeetcodeSnapshot(
                user_id=user.id,
                pulled_at=datetime.now(timezone.utc),
                tag=tag,
                solved_count=count,
                difficulty=None,
            )
        )

    resolved = await resolve_skills(set(tag_counts.keys()), db)

    tags_report: list[dict] = []
    evidence_created = 0
    evidence_updated = 0
    evidence_unchanged = 0

    for tag, count in tag_counts.items():
        canonical = resolved.get(tag)
        skill_updated = False

        if canonical is not None:
            skill = await get_or_create_skill(db, canonical, tag)
            prev_count = previous_tag_counts.get(tag)

            if skill.id not in existing_evidence_skill_ids:
                # First time this skill has ever gotten leetcode evidence.
                db.add(
                    SkillEvidence(
                        skill_id=skill.id,
                        source_type="leetcode_tag",
                        source_id=None,
                        weight=WEIGHTS["leetcode_tag"],
                    )
                )
                existing_evidence_skill_ids.add(skill.id)
                evidence_created += 1
                skill_updated = True
            elif prev_count is not None and count > prev_count:
                # Evidence already exists (weight is fixed per §4.3), but a
                # rising solved-count is still worth surfacing as activity —
                # without inserting a second, redundant evidence row.
                evidence_updated += 1
                skill_updated = True
            else:
                evidence_unchanged += 1

        tags_report.append({"tag": tag, "solved": count, "skill_updated": skill_updated})

    await db.flush()

    snapshot_skills_json = {"leetcode_tags_synced": list(tag_counts.keys())}
    if extra_stats:
        snapshot_skills_json["stats"] = extra_stats

    snapshot = ProfileSnapshot(
        user_id=user.id,
        taken_at=datetime.now(timezone.utc),
        skills_json=snapshot_skills_json,
        note=note,
    )
    db.add(snapshot)
    await db.flush()
    await db.commit()

    return {
        "status": "success",
        "synced_at": snapshot.taken_at.isoformat(),
        "user_id": str(user.id),
        "snapshot_id": str(snapshot.id),
        "summary": {
            "total_solved": extra_stats.get("total_solved") if extra_stats else None,
            "easy": extra_stats.get("easy") if extra_stats else None,
            "medium": extra_stats.get("medium") if extra_stats else None,
            "hard": extra_stats.get("hard") if extra_stats else None,
            "contest_rating": extra_stats.get("contest_rating") if extra_stats else None,
            "global_ranking": extra_stats.get("global_ranking") if extra_stats else None,
            "active_days_last_30": extra_stats.get("active_days_last_30") if extra_stats else None,
            "longest_streak": extra_stats.get("longest_streak") if extra_stats else None,
            "current_streak": extra_stats.get("current_streak") if extra_stats else None,
        },
        "tags": tags_report,
        "skill_evidence": {
            "created": evidence_created,
            "updated": evidence_updated,
            "unchanged": evidence_unchanged,
        },
        "profile_snapshot_created": True,
    }


async def sync_leetcode(db: AsyncSession, username: str) -> dict:
    print(f"[TRACING] Starting LeetCode sync for {username}...", flush=True)
    profile = await fetch_leetcode_profile(username)
    print(f"[TRACING] LeetCode sync fetched {len(profile['tag_counts'])} tags.", flush=True)

    extra_stats = {k: v for k, v in profile.items() if k != "tag_counts"}
    result = await _persist_leetcode_data(
        db, profile["tag_counts"], note="leetcode sync", extra_stats=extra_stats
    )
    print(f"[TRACING] LeetCode sync complete.", flush=True)
    return result


async def sync_leetcode_manual(db: AsyncSession, tag_counts: dict[str, int]) -> dict:
    # No difficulty/contest/streak data available from the manual form —
    # those fields come back as null in the report rather than fabricated.
    print(f"[TRACING] Persisting manual LeetCode submission ({len(tag_counts)} tags)...", flush=True)
    result = await _persist_leetcode_data(db, tag_counts, note="leetcode manual submission")
    print(f"[TRACING] Manual LeetCode submission persisted.", flush=True)
    return result