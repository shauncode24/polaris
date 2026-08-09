# backend/app/services/job_intelligence/interview_focus.py
"""Stage 8 — role-level interview focus areas, independent of any
candidate. Deterministic mapping from required skills + architecture
topics + seniority, per the design doc's documented two-tier pattern
(cheap deterministic pass now; an optional LLM refinement pass is left
as a future extension, same reasoning as seniority.py).
"""
from app.schemas.job_intelligence import EnrichedSkill, SeniorityLevel

MAX_INTERVIEW_FOCUS_AREAS = 10


def derive_interview_focus_areas(
    enriched_required: list[EnrichedSkill],
    architecture_topics: list[str],
    seniority: SeniorityLevel,
) -> list[str]:
    areas: list[str] = [s.canonical.replace("_", " ").title() for s in enriched_required]
    areas.extend(architecture_topics)

    if seniority.level in ("senior", "staff"):
        areas.append("System design & trade-off reasoning")
    if seniority.level == "staff":
        areas.append("Cross-team technical leadership")

    seen: set[str] = set()
    deduped: list[str] = []
    for area in areas:
        key = area.lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(area)
    return deduped[:MAX_INTERVIEW_FOCUS_AREAS]