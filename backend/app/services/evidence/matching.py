"""Finding a skill in free text, and the other names a skill goes by.

Resume ingestion decides which sources back a skill with `mentions_skill`;
the skill-gap evidence view uses the same rule to point at the sentence or
bullet that shows it. Nothing here calls an LLM.
"""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.structure import SkillAlias
from app.services.resume.skill_classifier import CANONICAL_SKILLS


def mentions_skill(text: str, raw_name: str) -> bool:
    """True when `raw_name` appears in `text` as its own word."""
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(raw_name.lower()) + r"(?![a-zA-Z0-9])"
    return re.search(pattern, text.lower()) is not None


def mentions_any(text: str, names: set[str]) -> bool:
    return any(mentions_skill(text, name) for name in names)


async def skill_aliases(db: AsyncSession, canonicals: set[str]) -> dict[str, set[str]]:
    """canonical skill -> every lower-case spelling known to mean it."""
    aliases = {c: {c.lower(), c.lower().replace("_", " ")} for c in canonicals}
    for raw, canonical in CANONICAL_SKILLS.items():
        if canonical in aliases:
            aliases[canonical].add(raw)
    if canonicals:
        cached = await db.execute(
            select(SkillAlias.raw_string, SkillAlias.canonical_name)
            .where(SkillAlias.canonical_name.in_(canonicals), SkillAlias.is_valid_skill.is_(True))
        )
        for raw, canonical in cached.all():
            aliases[canonical].add(raw.lower())
    return aliases


async def known_canonicals(db: AsyncSession, raw_strings: set[str]) -> dict[str, str]:
    """raw string -> canonical skill, using only what is already known (the
    built-in table and the cached classifications). Unknown strings are left
    out rather than sent to an LLM.
    """
    resolved: dict[str, str] = {}
    unknown: dict[str, str] = {}
    for raw in raw_strings:
        key = raw.strip().lower()
        if key in CANONICAL_SKILLS:
            resolved[raw] = CANONICAL_SKILLS[key]
        else:
            unknown[key] = raw
    if unknown:
        cached = await db.execute(
            select(SkillAlias.raw_string, SkillAlias.canonical_name)
            .where(SkillAlias.raw_string.in_(unknown), SkillAlias.is_valid_skill.is_(True))
        )
        for raw_key, canonical in cached.all():
            if canonical:
                resolved[unknown[raw_key]] = canonical
    return resolved
