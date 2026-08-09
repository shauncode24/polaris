# backend/app/services/job_intelligence/interview_focus.py
"""Stage 8 — role-level interview focus areas, independent of any
candidate. Deterministic mapping from required skills + architecture
topics + seniority, per the design doc's documented two-tier pattern
(cheap deterministic pass now; an optional LLM refinement pass is left
as a future extension, same reasoning as seniority.py).

Cap bumped from 10 -> 14 (review finding #7): required_skills now
captures process/practice requirements (git workflows, design
patterns, SDLC, DB queries) as well as named products, so a genuinely
detailed JD produces more real explicit focus areas than before — the
old cap of 10 would have silently truncated some of exactly the newly
captured items this fix was meant to surface.
"""
from app.schemas.job_intelligence import EnrichedSkill, SeniorityLevel

MAX_INTERVIEW_FOCUS_AREAS = 14


def derive_interview_focus_areas(
    enriched_required: list[EnrichedSkill],
    architecture_topics: list[str],
    seniority: SeniorityLevel,
) -> tuple[list[str], list[str], list[str]]:
    # Explicit focus: from required skills and architecture topics
    explicit: list[str] = [s.canonical.replace("_", " ").title() for s in enriched_required]
    explicit.extend(architecture_topics)

    # Inferred focus: seniority-driven additions
    inferred: list[str] = []
    if seniority.level in ("senior", "staff"):
        inferred.append("System design & trade-off reasoning")
    if seniority.level == "staff":
        inferred.append("Cross-team technical leadership")

    # De-duplicate explicit
    seen_explicit = set()
    deduped_explicit = []
    for item in explicit:
        key = item.lower().strip()
        if key and key not in seen_explicit:
            seen_explicit.add(key)
            deduped_explicit.append(item)

    # Combined is explicit + inferred, capped to MAX_INTERVIEW_FOCUS_AREAS
    combined = list(deduped_explicit)
    seen_combined = set(seen_explicit)
    for item in inferred:
        key = item.lower().strip()
        if key and key not in seen_combined:
            seen_combined.add(key)
            combined.append(item)

    capped_combined = combined[:MAX_INTERVIEW_FOCUS_AREAS]

    # Filter explicit and inferred down to only what is present in the capped combined list
    capped_set = {x.lower().strip() for x in capped_combined}
    final_explicit = [x for x in deduped_explicit if x.lower().strip() in capped_set]
    final_inferred = [x for x in inferred if x.lower().strip() in capped_set]

    return final_explicit, final_inferred, capped_combined