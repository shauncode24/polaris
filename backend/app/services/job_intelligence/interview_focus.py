# backend/app/services/job_intelligence/interview_focus.py
"""Stage 8 — role-level interview focus areas, independent of any
candidate. Deterministic mapping from required skills + architecture
topics + seniority, per the design doc's documented two-tier pattern
(cheap deterministic pass now; an optional LLM refinement pass is left
as a future extension, same reasoning as seniority.py).

Explicit vs. Inferred (review finding — interview_focus correctness):
  "explicit"  — topics the JD literally states will be assessed in the
                 interview process (very rare in standard JDs; most JDs
                 never say "the interview will cover X"). Default: [].
  "inferred"  — topics a candidate SHOULD prepare for, derived
                 deterministically from required skills + architecture
                 topics + seniority signals. This is what a JD's
                 required_skills section translates into for a candidate's
                 interview prep — the JD didn't say "we'll test React" but
                 a competent preparation guide would include it.

Cap bumped from 10 -> 14 (review finding #7): required_skills now
captures process/practice requirements (git workflows, design
patterns, SDLC, DB queries) as well as named products, so a genuinely
detailed JD produces more real inferred focus areas than before.
"""
from app.schemas.job_intelligence.job_intelligence import EnrichedSkill, SeniorityLevel

MAX_INTERVIEW_FOCUS_AREAS = 14


def derive_interview_focus_areas(
    enriched_required: list[EnrichedSkill],
    architecture_topics: list[str],
    seniority: SeniorityLevel,
) -> tuple[list[str], list[str], list[str]]:
    # Explicit: ONLY topics the JD literally states as interview content.
    # Standard JDs almost never say this, so this defaults to [].
    # Reserved for future use when a JD has an "Interview Process" section.
    explicit: list[str] = []

    # Inferred: required skills + architecture topics + seniority additions.
    # These are preparation signals derived from what the role demands,
    # NOT confirmed interview content.
    inferred_raw: list[str] = []
    for skill in enriched_required:
        # Use the canonical form but display-formatted (spaces, title case)
        display = skill.canonical.replace("_", " ").title()
        if display:
            inferred_raw.append(display)
    inferred_raw.extend(architecture_topics)

    # Seniority-driven additions
    if seniority.level in ("senior", "staff"):
        inferred_raw.append("System design & trade-off reasoning")
    if seniority.level == "staff":
        inferred_raw.append("Cross-team technical leadership")

    # De-duplicate inferred
    seen: set[str] = set()
    inferred: list[str] = []
    for item in inferred_raw:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            inferred.append(item)

    # Combined is explicit + inferred, capped
    combined = list(explicit)
    seen_combined = set(x.lower().strip() for x in explicit)
    for item in inferred:
        key = item.lower().strip()
        if key and key not in seen_combined:
            seen_combined.add(key)
            combined.append(item)

    capped_combined = combined[:MAX_INTERVIEW_FOCUS_AREAS]

    # Filter inferred down to only what survived the cap
    capped_set = {x.lower().strip() for x in capped_combined}
    final_inferred = [x for x in inferred if x.lower().strip() in capped_set]

    return explicit, final_inferred, capped_combined