# backend/app/services/interview/competency_tagging.py
"""Competency tagging for Project/Experience evidence — Interview Agent
implementation plan §C/§D. Tags each piece of resume evidence with which
interview competencies it demonstrates (leadership, teamwork, ownership,
...), so retrieval (context_builder.py) can RANK evidence by relevance
to the ACTUAL question being asked instead of handing the LLM the
entire profile every time, undifferentiated, on every call.

Two tiers, cheapest first — same philosophy as
resume/skill_classifier.py's CANONICAL_SKILLS / SkillAlias split:

  1. Deterministic keyword match over the item's own bullet/description
     text (COMPETENCY_KEYWORDS below). Free, instant, covers a large
     share of real, story-shaped bullets.
  2. Only for items where tier 1 finds NOTHING and the text is
     non-empty: one batched LLM call, cached forever in
     CompetencyTagAlias by a hash of the input text, so the same bullet
     — any user, any project — is never re-classified twice.

Tagging never invents evidence — it only labels which REAL text a piece
of evidence already contains. A tag is descriptive, not a score;
context_builder.py is what turns tags into a ranking.
"""
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.structure import CompetencyTagAlias
from app.prompts.interview.competency_tagging import COMPETENCY_TAGGING_SYSTEM_PROMPT
from app.schemas.interview.competency_tagging import CompetencyTagBatch

CANONICAL_COMPETENCIES: frozenset[str] = frozenset({
    "leadership", "teamwork", "conflict_resolution", "ownership",
    "problem_solving", "technical_depth", "failure_recovery", "mentorship",
})

# Hand-seeded, deliberately small — same "cheap and explainable" rule as
# github_commit_hygiene.py's GENERIC_MESSAGES and shared_signals.py's
# STRONG_ACTION_VERBS. Extend by hand as real bullets show a genuine
# tier-1 miss, rather than trying to enumerate every possible phrasing.
COMPETENCY_KEYWORDS: dict[str, list[str]] = {
    "leadership": ["led ", "spearheaded", "directed the", "drove the", "coordinated", "owned the roadmap"],
    "teamwork": ["collaborated", "worked closely with", "paired with", "cross-functional", "team of"],
    "conflict_resolution": ["disagreement", "conflict", "pushback", "differing opinion", "resolved a dispute", "aligned stakeholders"],
    "ownership": ["owned ", "took ownership", "end-to-end", "end to end", "solely responsible", "single-handedly", "drove the decision"],
    "problem_solving": ["debugged", "root cause", "diagnosed", "troubleshot", "resolved a critical", "fixed a critical"],
    "technical_depth": ["architected", "designed the system", "optimized", "scaled", "built from scratch", "implemented a"],
    "failure_recovery": ["failed", "mistake", "rolled back", "postmortem", "learned from", "incorrect assumption"],
    "mentorship": ["mentored", "onboarded", "trained", "taught", "guided a junior"],
}

MAX_ITEMS_PER_LLM_BATCH = 20


def tag_text_deterministic(text: str) -> list[str]:
    """Tier 1 — pure keyword match, no I/O. Returns a sorted list (may
    be empty) of every competency whose keyword set matches.
    """
    lowered = (text or "").lower()
    tags = [c for c, kws in COMPETENCY_KEYWORDS.items() if any(kw in lowered for kw in kws)]
    return sorted(tags)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


async def _classify_via_llm(texts_by_key: dict[str, str]) -> dict[str, list[str]]:
    payload = [{"key": k, "text": t[:800]} for k, t in texts_by_key.items()]
    response = await chat_completion(
        model=MODEL,
        messages=[
            {"role": "system", "content": COMPETENCY_TAGGING_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content
    parsed = CompetencyTagBatch.model_validate(json.loads(content))

    out: dict[str, list[str]] = {}
    for item in parsed.results:
        out[item.key] = sorted({t for t in item.tags if t in CANONICAL_COMPETENCIES})
    # Defensive fallback: never let a dropped key silently disappear —
    # same rule skill_classifier._classify_via_llm applies.
    for key in texts_by_key:
        out.setdefault(key, [])
    return out


async def tag_or_backfill_items(db: AsyncSession, items: list[dict]) -> dict[str, list[str]]:
    """items: [{"key": str, "text": str, "existing_tags": list[str] | None}].
    Returns key -> sorted competency tags.

    "existing_tags" being non-None means the caller already has a
    persisted value (Project.competency_tags / Experience.competency_tags
    is not NULL) — that value is trusted as-is and never re-derived,
    even if it's an empty list (an empty list is a real, previously-
    computed answer: "this text genuinely evidences no competency",
    not "not tagged yet").
    """
    results: dict[str, list[str]] = {}
    tier1_misses: dict[str, str] = {}

    for item in items:
        key = item["key"]
        existing = item.get("existing_tags")
        if existing is not None:
            results[key] = list(existing)
            continue

        text = item.get("text") or ""
        tier1 = tag_text_deterministic(text)
        if tier1 or not text.strip():
            results[key] = tier1
            continue

        tier1_misses[key] = text

    if not tier1_misses:
        return results

    hash_by_key = {k: _text_hash(t) for k, t in tier1_misses.items()}
    cache_result = await db.execute(
        select(CompetencyTagAlias).where(CompetencyTagAlias.text_hash.in_(set(hash_by_key.values())))
    )
    cached_by_hash = {row.text_hash: row.tags for row in cache_result.scalars().all()}

    still_unresolved: dict[str, str] = {}
    for key, h in hash_by_key.items():
        if h in cached_by_hash:
            results[key] = list(cached_by_hash[h])
        else:
            still_unresolved[key] = tier1_misses[key]

    if not still_unresolved:
        return results

    keys = list(still_unresolved.keys())
    for i in range(0, len(keys), MAX_ITEMS_PER_LLM_BATCH):
        batch_keys = keys[i : i + MAX_ITEMS_PER_LLM_BATCH]
        batch = {k: still_unresolved[k] for k in batch_keys}
        try:
            classified = await _classify_via_llm(batch)
        except Exception as e:
            print(f"[TRACING] Competency tagging LLM batch failed, leaving untagged: {e}", flush=True)
            classified = {k: [] for k in batch_keys}

        for key in batch_keys:
            tags = classified.get(key, [])
            results[key] = tags
            stmt = (
                pg_insert(CompetencyTagAlias)
                .values(text_hash=hash_by_key[key], tags=tags, created_at=datetime.now(timezone.utc))
                .on_conflict_do_nothing(index_elements=["text_hash"])
            )
            await db.execute(stmt)

    await db.flush()
    return results