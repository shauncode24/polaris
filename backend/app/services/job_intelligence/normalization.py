# backend/app/services/job_intelligence/normalization.py
"""Stage 3 — canonicalize every raw skill string the role requires and
attach category + curriculum-phase enrichment, plus (new) a clamped
proficiency_signal for skills that came with real JD proficiency
language (required_skills / nice_to_have — see ExtractedSkillRequirement).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.job_intelligence import EnrichedSkill, ExtractedSkillRequirement
from app.services.resume.skill_classifier import resolve_skills
from app.services.taxonomy.skill_taxonomy import CATEGORY_MAP, DEFAULT_CATEGORY, get_curriculum_phase

_VALID_PROFICIENCY_SIGNALS = {"good_knowledge", "hands_on", "exposure", "familiarity", "not_specified"}


def _normalize_proficiency(raw: str | None) -> str:
    """Never trust the LLM's proficiency_signal string blindly — same
    defensive pattern used everywhere else in this codebase (e.g.
    role_fit.py clamping role names, gap_analysis.py filtering
    priority_order).
    """
    return raw if raw in _VALID_PROFICIENCY_SIGNALS else "not_specified"


async def enrich_skill_requirements(
    items: list[ExtractedSkillRequirement], requirement_type: str, db: AsyncSession
) -> list[EnrichedSkill]:
    """For required_skills / nice_to_have — items carry real, JD-quoted
    proficiency language ("good knowledge of" vs "exposure to").
    """
    if not items:
        return []

    raw_strings = [i.skill for i in items]
    resolved = await resolve_skills(set(raw_strings), db)
    proficiency_by_raw = {i.skill: _normalize_proficiency(i.proficiency_signal) for i in items}

    enriched: list[EnrichedSkill] = []
    seen_canonicals: set[str] = set()
    for item in items:
        canonical = resolved.get(item.skill)
        if canonical is None or canonical in seen_canonicals:
            continue
        seen_canonicals.add(canonical)
        enriched.append(EnrichedSkill(
            raw=item.skill,
            canonical=canonical,
            category=CATEGORY_MAP.get(canonical, DEFAULT_CATEGORY),
            curriculum_phase=get_curriculum_phase(canonical),
            requirement_type=requirement_type,
            proficiency_signal=proficiency_by_raw.get(item.skill, "not_specified"),
        ))
    return enriched


async def enrich_skills(raw_strings: list[str], requirement_type: str, db: AsyncSession) -> list[EnrichedSkill]:
    """For implicit_skills — the model's own inference from a
    responsibility/phrase, never a literal quoted proficiency phrase, so
    proficiency_signal stays at its "not_specified" default.
    """
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