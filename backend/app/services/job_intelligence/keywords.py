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


from app.schemas.job_intelligence.job_intelligence import ResumeKeywordTiers

def derive_resume_keyword_tiers(
    enriched_required, enriched_implicit, enriched_nice,
    raw_required: list[str], raw_implicit: list[str], raw_nice: list[str],
    architecture_topics: list[str],
) -> ResumeKeywordTiers:
    # 1. Raw phrasings de-duplicated by normalized form
    raw_seen = set()
    raw_list = []
    for item in raw_required + raw_implicit + raw_nice + architecture_topics:
        cleaned = item.strip()
        if len(cleaned) < MIN_KEYWORD_LEN:
            continue
        norm = _normalize_keyword(cleaned)
        if norm and norm not in raw_seen:
            raw_seen.add(norm)
            raw_list.append(cleaned)

    # 2. Canonical forms
    canon_seen = set()
    canon_list = []
    for skill in enriched_required + enriched_implicit + enriched_nice:
        canon = skill.canonical
        if canon and canon not in canon_seen:
            canon_seen.add(canon)
            canon_list.append(canon)

    # 3. Resume relevant keywords
    relevant_dict = {}
    def add_relevant(candidate: str) -> None:
        candidate = candidate.strip()
        if len(candidate) < MIN_KEYWORD_LEN:
            return
        norm = _normalize_keyword(candidate)
        if not norm or norm in relevant_dict:
            return
        relevant_dict[norm] = candidate.lower()

    for skill in enriched_required + enriched_implicit + enriched_nice:
        add_relevant(skill.canonical.replace("_", " "))
    for raw in raw_required + raw_implicit + raw_nice:
        add_relevant(raw)
    for topic in architecture_topics:
        add_relevant(topic)

    return ResumeKeywordTiers(
        raw=sorted(raw_list),
        canonical=sorted(canon_list),
        resume_relevant=sorted(relevant_dict.values()),
    )