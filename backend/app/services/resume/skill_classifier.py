import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import client, MODEL
from app.models.structure import SkillAlias
from app.schemas.skill_classification import SkillClassificationBatch

# Tier 1: hand-seeded, instant, free. Covers the common cases you already
# know about. Anything not here falls through to tiers 2 and 3 below.
CANONICAL_SKILLS: dict[str, str] = {
    "react": "react", "reactjs": "react", "react.js": "react",
    "fastapi": "fastapi",
    "python": "python",
    "docker": "docker",
    "redis": "redis",
    "postgres": "postgres", "postgresql": "postgres",
    "typescript": "typescript",
    "javascript": "javascript", "js": "javascript",
    "sql server": "sql_server",
    "asp.net core": "aspnet_core", "asp.netcore": "aspnet_core", "aspnetcore": "aspnet_core",
    "c#": "csharp", "c sharp": "csharp",
    "ef core": "ef_core",
    "langgraph": "langgraph",
    "rest api": "rest_api", "restful api": "rest_api", "restful_api": "rest_api",
    "rest": "rest_api", "rest apis": "rest_api", "rest_apis": "rest_api",
    "node.js": "nodejs", "nodejs": "nodejs", "node": "nodejs",
    "express.js": "express", "expressjs": "express", "express": "express",
    "three.js": "threejs", "threejs": "threejs",
    "mongodb": "mongodb", "mongo": "mongodb",
    "vector search": "vector_search",
    "rag": "rag",
}

from app.prompts.classification import CLASSIFICATION_SYSTEM_PROMPT


async def _classify_via_llm(raw_strings: list[str]) -> dict[str, tuple[str | None, bool]]:
    """One batched LLM call for every raw string not already known, rather
    than one call per skill — keeps this cheap even for a resume with many
    unfamiliar terms.
    """
    user_content = json.dumps(raw_strings)
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content
    parsed = SkillClassificationBatch.model_validate(json.loads(content))

    output: dict[str, tuple[str | None, bool]] = {}
    for item in parsed.results:
        output[item.raw] = (item.canonical, item.is_valid_skill)

    # Defensive fallback: if the LLM dropped any input (skipped it in the
    # response), treat it as invalid rather than crashing the ingestion.
    for raw in raw_strings:
        if raw not in output:
            output[raw] = (None, False)

    return output


async def resolve_skills(raw_strings: set[str], db: AsyncSession) -> dict[str, str | None]:
    """Resolve every raw skill string to its canonical name, or None if it's
    not a real skill at all. Three tiers, cheapest first:

    1. Hardcoded dict  -> instant, free, zero DB/LLM calls
    2. skill_aliases DB cache -> instant, free, grows over time as new
       resumes are ingested (by any user)
    3. Batched LLM classification -> only for genuinely unseen strings,
       one call per ingestion run (not per skill), and every result is
       written back into the cache so it's never re-classified again.
    """
    results: dict[str, str | None] = {}
    unresolved: set[str] = set()

    for raw in raw_strings:
        key = raw.strip().lower()
        if key in CANONICAL_SKILLS:
            results[raw] = CANONICAL_SKILLS[key]
        else:
            unresolved.add(raw)

    if unresolved:
        lookup_keys = [r.strip().lower() for r in unresolved]
        cached = await db.execute(
            select(SkillAlias).where(SkillAlias.raw_string.in_(lookup_keys))
        )
        cached_by_key = {row.raw_string: row for row in cached.scalars().all()}

        still_unresolved: set[str] = set()
        for raw in unresolved:
            key = raw.strip().lower()
            if key in cached_by_key:
                row = cached_by_key[key]
                results[raw] = row.canonical_name if row.is_valid_skill else None
            else:
                still_unresolved.add(raw)
        unresolved = still_unresolved

    if unresolved:
        classified = await _classify_via_llm(list(unresolved))

        for raw, (canonical, is_valid) in classified.items():
            key = raw.strip().lower()
            results[raw] = canonical if is_valid else None

            # Persist this decision so future ingestions (any user, any
            # resume) never need to ask the LLM about this string again.
            stmt = (
                pg_insert(SkillAlias)
                .values(raw_string=key, canonical_name=canonical, is_valid_skill=is_valid)
                .on_conflict_do_nothing(index_elements=["raw_string"])
            )
            await db.execute(stmt)

        await db.flush()

    return results