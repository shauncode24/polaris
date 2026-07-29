# backend/app/services/leetcode/leetcode_recency.py
"""Derives, per LeetCode tag, the last time solved-count actually moved —
grounded entirely in the append-only leetcode_snapshots history that
already gets written on every sync. No new API calls, no guessing: a
tag's "last progress" date is the most recent pulled_at at which its
solved_count increased versus the prior sync for that tag.

This is what powers recency-aware mastery decay (leetcode_mastery.py)
without requiring per-problem solve dates, which the unofficial
LeetCode API simply doesn't expose.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import LeetcodeSnapshot
from app.services.leetcode.leetcode_taxonomy import TAG_TO_TOPIC


async def compute_tag_last_progress(db: AsyncSession, user_id) -> dict[str, datetime]:
    """tag_slug -> datetime of the most recent sync at which that tag's
    solved_count increased over its own previous value. A tag with only
    one historical row (first time ever synced) is NOT included here —
    there's no prior baseline to call "progress" against, so it's left
    out and callers should treat that as "no decay data yet."
    """
    result = await db.execute(
        select(LeetcodeSnapshot.tag, LeetcodeSnapshot.solved_count, LeetcodeSnapshot.pulled_at)
        .where(LeetcodeSnapshot.user_id == user_id)
        .order_by(LeetcodeSnapshot.tag, LeetcodeSnapshot.pulled_at)
    )
    rows = result.all()

    last_progress: dict[str, datetime] = {}
    prev_count_by_tag: dict[str, int] = {}

    for tag, solved_count, pulled_at in rows:
        prev = prev_count_by_tag.get(tag)
        if prev is not None and solved_count > prev:
            last_progress[tag] = pulled_at
        prev_count_by_tag[tag] = solved_count

    return last_progress


def compute_topic_recency(
    tag_last_progress: dict[str, datetime],
    tag_counts: dict[str, int],
) -> dict[str, datetime | None]:
    """topic -> most recent progress datetime across every tag that rolls
    up into it (freshest practice wins), or None if no tag under that
    topic has any recorded progress event yet. Only considers tags the
    user has actually solved at least one problem in.

    Real dates always take precedence over "unknown" (None) regardless
    of dict iteration order — a topic is only left at None if NONE of
    its constituent tags have a recorded progress event.
    """
    topic_recency: dict[str, datetime | None] = {}
    for tag, count in tag_counts.items():
        if count <= 0:
            continue
        topic = TAG_TO_TOPIC.get(tag)
        if topic is None:
            continue
        progress_at = tag_last_progress.get(tag)
        if progress_at is not None:
            existing = topic_recency.get(topic)
            if existing is None or progress_at > existing:
                topic_recency[topic] = progress_at
        elif topic not in topic_recency:
            topic_recency[topic] = None
    return topic_recency


def days_since(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - dt).days)