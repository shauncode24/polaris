# backend/app/services/leetcode/leetcode_sync.py
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import LeetcodeSnapshot
from app.models.inference import ProfileSnapshot, SkillEvidence, LeetcodePortfolioReview
from app.services.resume.confidence import WEIGHTS
from app.services.leetcode.leetcode_client import LeetCodeSyncError, fetch_leetcode_profile
from app.services.leetcode.leetcode_insights import build_leetcode_insights, build_plan_adherence
from app.services.leetcode.leetcode_recency import compute_tag_last_progress, compute_topic_recency, days_since
from app.services.leetcode.leetcode_taxonomy import topic_totals, weighted_topic_totals, TAG_TO_TOPIC, log_unmapped_tags
from app.services.resume.skill_classifier import resolve_skills
from app.services.user_helpers import get_or_create_skill

logger = logging.getLogger(__name__)

CONTEST_HISTORY_LIMIT = 12

_DEPTH_SCALE = 50.0
_MAX_DEPTH_MULTIPLIER = 2.0


def _depth_multiplier_for_score(weighted_score: float) -> float:
    return min(_MAX_DEPTH_MULTIPLIER, 1.0 + weighted_score / _DEPTH_SCALE)


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


async def _get_existing_evidence_skill_ids(db: AsyncSession, user_id) -> set:
    """FIX (cross-user evidence leak — actual functional bug, not just a
    leak): this previously checked skill_id membership GLOBALLY across
    all users. Two real bugs resulted: (1) if User A already had
    leetcode_tag evidence for a skill, User B's sync would treat that
    skill as "already existing" and silently skip creating User B's OWN
    evidence row for it; and (2) the companion UPDATE statement below
    had no user filter either, so User B's sync could overwrite User A's
    evidence weight outright. Both are fixed by scoping this query (and
    the UPDATE) to user_id.
    """
    result = await db.execute(
        select(SkillEvidence.skill_id).where(
            SkillEvidence.source_type == "leetcode_tag",
            SkillEvidence.user_id == user_id,
        )
    )
    return {row[0] for row in result.all()}


async def _get_previous_leetcode_stats(db: AsyncSession, user_id) -> dict | None:
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


async def _get_contest_rating_history(db: AsyncSession, user_id, limit: int = CONTEST_HISTORY_LIMIT) -> list[dict]:
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note.in_(["leetcode sync", "leetcode manual submission"]))
        .order_by(ProfileSnapshot.taken_at.asc())
        .limit(limit)
    )
    history = []
    for snapshot in result.scalars().all():
        stats = snapshot.skills_json.get("stats") if isinstance(snapshot.skills_json, dict) else None
        rating = stats.get("contest_rating") if stats else None
        history.append({"taken_at": snapshot.taken_at.isoformat(), "rating": rating})
    return history


async def _get_latest_recommended_topics(db: AsyncSession, user_id) -> tuple[list[str], str | None]:
    result = await db.execute(
        select(LeetcodePortfolioReview)
        .where(LeetcodePortfolioReview.user_id == user_id)
        .order_by(LeetcodePortfolioReview.created_at.desc())
        .limit(1)
    )
    review = result.scalar_one_or_none()
    if review is None or not isinstance(review.review_json, dict):
        return [], None
    topics = review.review_json.get("target_focus_topics", [])
    return topics, review.created_at.isoformat()


async def _persist_leetcode_data(
    db: AsyncSession,
    user,
    tag_counts: dict[str, int],
    note: str,
    extra_stats: dict | None = None,
    tag_difficulty_tier: dict[str, str] | None = None,
) -> dict:
    previous_tag_counts = await _get_previous_tag_counts(db, user.id)
    existing_evidence_skill_ids = await _get_existing_evidence_skill_ids(db, user.id)
    previous_stats = await _get_previous_leetcode_stats(db, user.id)
    contest_rating_history = await _get_contest_rating_history(db, user.id)
    recommended_topics, recommended_at = await _get_latest_recommended_topics(db, user.id)

    unmapped = log_unmapped_tags(tag_counts)
    if unmapped:
        logger.debug("Found %d unmapped LeetCode tags: %s", len(unmapped), sorted(unmapped))

    for tag, count in tag_counts.items():
        db.add(
            LeetcodeSnapshot(
                user_id=user.id, pulled_at=datetime.now(timezone.utc),
                tag=tag, solved_count=count, difficulty=None,
            )
        )

    weighted_totals_by_topic = weighted_topic_totals(tag_counts, tag_difficulty_tier)
    tag_weighted_score: dict[str, float] = {}
    for tag in tag_counts:
        topic = TAG_TO_TOPIC.get(tag)
        if topic is not None:
            tag_weighted_score[tag] = weighted_totals_by_topic.get(topic, 0.0)

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
            weighted_score = tag_weighted_score.get(tag, 0.0)
            depth_weight = WEIGHTS["leetcode_tag"] * _depth_multiplier_for_score(weighted_score)

            if skill.id not in existing_evidence_skill_ids:
                db.add(SkillEvidence(
                    user_id=user.id,
                    skill_id=skill.id, source_type="leetcode_tag",
                    source_id=None, weight=depth_weight,
                ))
                existing_evidence_skill_ids.add(skill.id)
                new_skills.append(canonical)
                skill_updated = True
            elif prev_count is not None and count > prev_count:
                await db.execute(
                    update(SkillEvidence)
                    .where(SkillEvidence.skill_id == skill.id)
                    .where(SkillEvidence.source_type == "leetcode_tag")
                    .where(SkillEvidence.user_id == user.id)
                    .values(weight=depth_weight)
                )
                reinforced_skills.append(canonical)
                skill_updated = True
            else:
                unchanged_skills.append(canonical)

        tags_report.append({"tag": tag, "solved": count, "skill_updated": skill_updated})

    await db.flush()

    tag_last_progress = await compute_tag_last_progress(db, user.id)
    topic_recency = compute_topic_recency(tag_last_progress, tag_counts)
    topic_days_since = {topic: days_since(dt) for topic, dt in topic_recency.items()}

    current_topic_totals = topic_totals(tag_counts)
    previous_topic_totals_for_adherence = topic_totals(previous_tag_counts) if previous_tag_counts else {}

    if extra_stats and extra_stats.get("contest_rating") is not None:
        contest_rating_history = contest_rating_history + [{
            "taken_at": datetime.now(timezone.utc).isoformat(),
            "rating": extra_stats.get("contest_rating"),
        }]

    plan_adherence = build_plan_adherence(
        recommended_topics, recommended_at, current_topic_totals, previous_topic_totals_for_adherence
    )

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
        topic_days_since=topic_days_since,
        contest_rating_history=contest_rating_history,
        plan_adherence=plan_adherence,
        tag_difficulty_tier=tag_difficulty_tier,
    )

    snapshot_skills_json = {"leetcode_tags_synced": list(tag_counts.keys()), "insights": insights}
    if tag_difficulty_tier:
        snapshot_skills_json["tag_difficulty_tier"] = tag_difficulty_tier
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
    logger.info("Starting LeetCode sync for %s...", username)
    profile = await fetch_leetcode_profile(username)
    logger.info("LeetCode sync fetched %d tags.", len(profile["tag_counts"]))
    tag_difficulty_tier = profile.get("tag_difficulty_tier", {})
    extra_stats = {k: v for k, v in profile.items() if k not in ("tag_counts", "tag_difficulty_tier")}
    result = await _persist_leetcode_data(
        db, user, profile["tag_counts"], note="leetcode sync",
        extra_stats=extra_stats, tag_difficulty_tier=tag_difficulty_tier,
    )
    logger.info("LeetCode sync complete.")
    return result


async def sync_leetcode_manual(db: AsyncSession, user, tag_counts: dict[str, int]) -> dict:
    logger.info("Persisting manual LeetCode submission (%d tags)...", len(tag_counts))
    result = await _persist_leetcode_data(db, user, tag_counts, note="leetcode manual submission")
    logger.info("Manual LeetCode submission persisted.")
    return result