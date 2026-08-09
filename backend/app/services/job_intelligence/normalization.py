# backend/app/services/job_intelligence/normalization.py
"""Stage 3 — canonicalize every raw skill string the role requires and
attach category + curriculum-phase enrichment. Reuses resolve_skills()
unchanged (it's already user-independent — see skill_classifier.py's
own docstring); this module never touches user data.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.job_intelligence import EnrichedSkill
from app.services.resume.skill_classifier import resolve_skills
from app.services.taxonomy.skill_taxonomy import CATEGORY_MAP, DEFAULT_CATEGORY, get_curriculum_phase


async def enrich_skills(
    raw_strings: list[str], requirement_type: str, db: AsyncSession
) -> list[EnrichedSkill]:
    if not raw_strings:
        return []

    resolved = await resolve_skills(set(raw_strings), db)

    enriched: list[EnrichedSkill] = []
    seen_canonicals: set[str] = set()
    for raw in raw_strings:
        canonical = resolved.get(raw)
        if canonical is None or canonical in seen_canonicals:
            continue
        seen_canonicals.add(canonical)
        enriched.append(EnrichedSkill(
            raw=raw,
            canonical=canonical,
            category=CATEGORY_MAP.get(canonical, DEFAULT_CATEGORY),
            curriculum_phase=get_curriculum_phase(canonical),
            requirement_type=requirement_type,
        ))
    return enriched