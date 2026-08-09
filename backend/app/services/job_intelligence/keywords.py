# backend/app/services/job_intelligence/keywords.py
"""Stage 7 — the literal keyword set a resume/ATS pass should try to
surface for this role. Purely deterministic: union of raw requirement
strings (phrasing matters for ATS, not just canonical identity),
canonical display names, and architecture-topic phrases.
"""
from app.schemas.job_intelligence import EnrichedSkill


def derive_resume_keywords(
    enriched_required: list[EnrichedSkill],
    enriched_implicit: list[EnrichedSkill],
    raw_required: list[str],
    raw_implicit: list[str],
    architecture_topics: list[str],
) -> list[str]:
    keywords: set[str] = set()
    for skill in enriched_required + enriched_implicit:
        keywords.add(skill.canonical)
        keywords.add(skill.raw.strip().lower())
    for raw in raw_required + raw_implicit:
        if raw.strip():
            keywords.add(raw.strip().lower())
    for topic in architecture_topics:
        if topic.strip():
            keywords.add(topic.strip().lower())
    return sorted(keywords)