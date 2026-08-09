# backend/app/services/job_intelligence/normalization.py
"""Stage 3 — canonicalize every raw skill string the role requires and
attach category + curriculum-phase enrichment, plus a clamped
proficiency_signal for skills that came with real JD proficiency
language (required_skills / nice_to_have).

FIX (review finding #4 — required skills silently dropped): resolve_skills()
(services/resume/skill_classifier.py) was built to classify strings
pulled off a RESUME, where a process/practice phrase like "git
workflows" or "SDLC" correctly gets excluded as "not a concrete
technology" (see prompts/classification.py — is_valid_skill=false for
"processes"). A JD's required_skills line is a different kind of fact:
even when it names a process or practice rather than a product, it is
still something the role explicitly requires, and Job Intelligence must
not silently discard it just because the resume-oriented classifier
doesn't recognize it as a product. Any raw string resolve_skills can't
canonicalize now falls back to a normalized slug instead of being
dropped — see _fallback_canonicalize — and gets categorized via
taxonomy.categorize_skill's Process & Practice heuristic instead of
disappearing from enriched_required_skills entirely.
"""
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.job_intelligence import EnrichedSkill, ExtractedImplicitSkill, ExtractedSkillRequirement
from app.services.resume.skill_classifier import resolve_skills
from app.services.taxonomy.skill_taxonomy import categorize_skill, get_curriculum_phase

_VALID_PROFICIENCY_SIGNALS = {"good_knowledge", "hands_on", "exposure", "familiarity", "not_specified"}
_VALID_CONFIDENCE = {"low", "medium", "high"}


def _normalize_proficiency(raw: str | None) -> str:
    """Never trust the LLM's proficiency_signal string blindly — same
    defensive pattern used everywhere else in this codebase (e.g.
    role_fit.py clamping role names, gap_analysis.py filtering
    priority_order).
    """
    return raw if raw in _VALID_PROFICIENCY_SIGNALS else "not_specified"


def _normalize_confidence(raw: str | None) -> str:
    return raw if raw in _VALID_CONFIDENCE else "medium"


def _fallback_canonicalize(raw: str) -> str:
    """Used only when resolve_skills couldn't (or wouldn't) canonicalize
    a raw JD string — i.e. it decided this isn't a "real skill" by its
    own (resume-oriented) rules. Rather than dropping the requirement
    entirely, slugify it into a stable canonical form. Two JD phrasings
    of the same practice ("Git workflows" vs. "git workflow") still
    collapse to the same slug, preserving the same dedup guarantee
    resolve_skills gives for real products.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", raw.strip().lower()).strip("_")
    return slug or raw.strip().lower()


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
        # FIX (review finding #4): fall back to a slug instead of
        # dropping the entry when resolve_skills has no canonical for
        # it — see module docstring.
        canonical = resolved.get(item.skill) or _fallback_canonicalize(item.skill)
        if canonical in seen_canonicals:
            continue
        seen_canonicals.add(canonical)
        enriched.append(EnrichedSkill(
            raw=item.skill,
            canonical=canonical,
            category=categorize_skill(canonical, item.skill),
            curriculum_phase=get_curriculum_phase(canonical),
            requirement_type=requirement_type,
            proficiency_signal=proficiency_by_raw.get(item.skill, "not_specified"),
        ))
    return enriched


async def enrich_skills(
    items: list[ExtractedImplicitSkill], requirement_type: str, db: AsyncSession
) -> list[EnrichedSkill]:
    """For implicit_skills — each item carries the model's own real
    evidence (the responsibility/phrase it was inferred from) and a
    confidence level, never a literal quoted proficiency phrase — see
    ExtractedImplicitSkill's docstring / review finding #5. Both are
    carried through onto the resulting EnrichedSkill so a consumer can
    tell an inference apart from a direct JD citation.
    """
    if not items:
        return []

    raw_strings = [i.skill for i in items]
    resolved = await resolve_skills(set(raw_strings), db)

    enriched: list[EnrichedSkill] = []
    seen_canonicals: set[str] = set()
    for item in items:
        canonical = resolved.get(item.skill) or _fallback_canonicalize(item.skill)
        if canonical in seen_canonicals:
            continue
        seen_canonicals.add(canonical)
        enriched.append(EnrichedSkill(
            raw=item.skill,
            canonical=canonical,
            category=categorize_skill(canonical, item.skill),
            curriculum_phase=get_curriculum_phase(canonical),
            requirement_type=requirement_type,
            evidence=item.evidence,
            confidence=_normalize_confidence(item.confidence),
        ))
    return enriched