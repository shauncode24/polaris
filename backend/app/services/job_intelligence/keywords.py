# backend/app/services/job_intelligence/keywords.py
"""Stage 7 — the literal keyword set a resume/ATS pass should try to
surface for this role. Deduplicates by NORMALIZED form (lowercased,
punctuation/underscores collapsed to spaces) so a canonical name like
"data_structures_algorithms" and a raw JD phrase like "Data Structures &
Algorithms" collapse to one entry instead of both surviving as
near-duplicates (audit point #16). Canonical (spaced) forms are added
first, so they "win" the display string when a raw form is a duplicate.
"""
import re

MIN_KEYWORD_LEN = 2


def _normalize_keyword(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def derive_resume_keywords(
    enriched_required, enriched_implicit,
    raw_required: list[str], raw_implicit: list[str],
    architecture_topics: list[str],
) -> list[str]:
    keywords: dict[str, str] = {}  # normalized form -> chosen display string

    def add(candidate: str) -> None:
        candidate = candidate.strip()
        if len(candidate) < MIN_KEYWORD_LEN:
            return
        norm = _normalize_keyword(candidate)
        if not norm or norm in keywords:
            return
        keywords[norm] = candidate.lower()

    for skill in enriched_required + enriched_implicit:
        add(skill.canonical.replace("_", " "))
    for raw in raw_required + raw_implicit:
        add(raw)
    for topic in architecture_topics:
        add(topic)

    return sorted(keywords.values())