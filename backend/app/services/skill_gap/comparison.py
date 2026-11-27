# backend/app/services/skill_gap/comparison.py
"""Core have/partial/missing loop — moved from jobs/gap_analysis.py.
Now takes a JobIntelligenceProfile instead of a raw canonical_skills
dict + architecture_topics list; the role-intrinsic priority ordering
(band boundaries) is derived here from the profile's own
requirement_type + curriculum_phase, then handed to the narrowed
prioritize_missing_skills() as a given, per design doc §5.4.
"""
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_intelligence import JobIntelligenceProfileRow
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.schemas.skill_gap.skill_gap import (
    REPORT_VERSION,
    HaveSkill,
    MissingSkill,
    PartialSkill,
    SkillGapReport,
    SupportingEvidence,
)
from app.services.evidence.confidence import (
    get_active_skill_evidence,
    get_hidden_skill_names,
    get_reconciled_skill_confidences,
)
from app.services.evidence.supporting import build_supporting_evidence, evidence_labels
from app.services.resume.review import classify_match
from app.services.skill_gap.effort_estimation import estimate_weeks
from app.services.skill_gap.prioritization import PrioritizationError, prioritize_missing_skills
from app.services.skill_gap.severity import gap_severity
from app.services.taxonomy.skill_taxonomy import get_curriculum_rank
import logging

logger = logging.getLogger(__name__)

_BAND_ORDER = {"required": 0, "implicit": 1, "nice_to_have": 2}


async def _historical_skill_frequency(db: AsyncSession, user_id) -> Counter:
    """How often each canonical skill appears across all of this user's
    parsed jobs (a job counts a skill once, however many bands list it).
    """
    result = await db.execute(
        select(JobIntelligenceProfileRow.profile_json).where(JobIntelligenceProfileRow.user_id == user_id)
    )
    counter: Counter = Counter()
    for (profile,) in result.all():
        if not profile:
            continue
        canonicals: set[str] = set()
        for group in ("enriched_required_skills", "enriched_implicit_skills", "enriched_nice_to_have"):
            for skill in profile.get(group) or []:
                canonical = skill.get("canonical") if isinstance(skill, dict) else None
                if canonical:
                    canonicals.add(canonical)
        counter.update(canonicals)
    return counter


def _role_priority_order(missing_skill_names: list[str], canonical_skills: dict[str, str]) -> list[str]:
    """Band order (required -> implicit -> nice_to_have), sub-sequenced
    by curriculum rank within each band — the deterministic,
    role-intrinsic ordering Job Intelligence has already decided. This
    is the hard constraint the LLM adjustment step must never cross.
    """
    return sorted(
        missing_skill_names,
        key=lambda s: (_BAND_ORDER.get(canonical_skills.get(s, "nice_to_have"), 2), get_curriculum_rank(s)),
    )


def _fallback_prioritization(
    missing_skill_names: list[str], frequency: Counter, role_priority_order: list[str]
) -> tuple[list[str], dict[str, int]]:
    order_index = {s: i for i, s in enumerate(role_priority_order)}
    ordered = sorted(
        missing_skill_names,
        key=lambda s: (order_index.get(s, len(role_priority_order)), -frequency.get(s, 0)),
    )
    weeks = {s: estimate_weeks(1) for s in ordered}
    return ordered, weeks


def _enforce_band_boundaries(
    llm_order: list[str], role_priority_order: list[str], canonical_skills: dict[str, str]
) -> list[str]:
    """Never trust the LLM's re-ordering blindly across a band boundary
    — same defensive pattern used everywhere else in this codebase.
    Re-sorts llm_order stably by band first, preserving the LLM's
    within-band ordering.
    """
    order_index = {s: i for i, s in enumerate(llm_order)}
    return sorted(
        role_priority_order,
        key=lambda s: (
            _BAND_ORDER.get(canonical_skills.get(s, "nice_to_have"), 2),
            order_index.get(s, len(llm_order)),
        ),
    )


async def analyze_skill_gap(
    db: AsyncSession,
    user_id,
    job_intelligence: JobIntelligenceProfile,
) -> SkillGapReport:
    canonical_skills = job_intelligence.canonical_skills_map
    role = job_intelligence.role
    company = job_intelligence.company

    if not canonical_skills:
        return SkillGapReport(
            have=[], partial=[], missing=[], priority_order=[], estimated_weeks=0,
            evidence_version=REPORT_VERSION,
        )

    view = await load_evidence_view(db, user_id, set(canonical_skills))
    have, partial, missing = match_requirements(canonical_skills, view)

    frequency = await _historical_skill_frequency(db, user_id)
    missing_names = [m.skill for m in missing]

    if missing_names:
        role_priority_order = _role_priority_order(missing_names, canonical_skills)
        try:
            context = {
                "role": role,
                "company": company,
                "role_priority_order": role_priority_order,
                "have": [{"skill": h.skill, "confidence": h.confidence} for h in have],
                "partial": [{"skill": p.skill, "confidence": p.confidence} for p in partial],
                "missing": missing_names,
            }
            result = await prioritize_missing_skills(context)

            valid_priority = [s for s in result.priority_order if s in missing_names]
            for s in missing_names:
                if s not in valid_priority:
                    valid_priority.append(s)
            valid_priority = _enforce_band_boundaries(valid_priority, role_priority_order, canonical_skills)

            weeks_by_skill = {
                s: max(1, result.estimated_weeks.get(s, estimate_weeks(1))) for s in missing_names
            }
        except PrioritizationError as e:
            logger.warning("Prioritization degraded, using role-order fallback: %s", e)
            valid_priority, weeks_by_skill = _fallback_prioritization(missing_names, frequency, role_priority_order)
    else:
        valid_priority, weeks_by_skill = [], {}

    for m in missing:
        m.estimated_weeks = weeks_by_skill.get(m.skill, 0)

    missing.sort(key=lambda m: get_curriculum_rank(m.skill))
    total_weeks = sum(weeks_by_skill.values()) if weeks_by_skill else estimate_weeks(len(missing))

    return SkillGapReport(
        have=have, partial=partial, missing=missing,
        priority_order=valid_priority, estimated_weeks=total_weeks,
        evidence_version=REPORT_VERSION,
    )


@dataclass
class EvidenceView:
    """What a user's record says about a set of skills, read once so several
    jobs can be matched against it.
    """
    reconciled: dict[str, dict]
    supporting: dict[str, list[SupportingEvidence]]
    hidden: set[str]


async def load_evidence_view(db: AsyncSession, user_id, canonicals: set[str]) -> EvidenceView:
    # The same confidence every other feature reads (claim-risk and timeline
    # discounts applied; hidden and superseded evidence excluded), plus the
    # concrete items behind it.
    reconciled = await get_reconciled_skill_confidences(db, user_id)
    active_evidence = await get_active_skill_evidence(db, user_id)
    supporting = await build_supporting_evidence(
        db, user_id, {c: rows for c, rows in active_evidence.items() if c in canonicals}
    )
    return EvidenceView(reconciled, supporting, await get_hidden_skill_names(db, user_id))


def match_requirements(
    canonical_skills: dict[str, str], view: EvidenceView
) -> tuple[list[HaveSkill], list[PartialSkill], list[MissingSkill]]:
    """Which of a job's requirements the user has, half has and lacks.
    Deterministic. `canonical_skills` maps each skill to how the job asks
    for it, and `view` must cover those skills.
    """
    have: list[HaveSkill] = []
    partial: list[PartialSkill] = []
    missing: list[MissingSkill] = []

    for canonical, requirement_type in canonical_skills.items():
        name = canonical.replace("_", " ").title()
        entry = view.reconciled.get(canonical)
        items = view.supporting.get(canonical, [])

        # A requirement only counts as met when there is something to point at.
        if entry is None or not items:
            if canonical in view.hidden:
                reason = "You hid this skill from your evidence record"
                explanation = f"{name} is hidden in your profile. Restore it there if it should count."
            else:
                reason = "No evidence found in profile"
                explanation = (
                    f"{name} wasn't matched because no verified evidence was found in your: "
                    f"Resume, Projects, or GitHub. If you've used {name}, "
                    f"add it to one of those sources and resync."
                )
            missing.append(MissingSkill(
                skill=canonical, reason=reason, explanation=explanation,
                severity=gap_severity(requirement_type, "missing"),
            ))
            continue

        confidence = entry["confidence"]
        bucket = classify_match(confidence)
        labels = evidence_labels(items)

        if bucket == "missing":
            missing.append(MissingSkill(
                skill=canonical,
                reason=f"Low confidence ({confidence:.2f}) — insufficient evidence",
                explanation=(
                    f"{name} wasn't matched because the verified evidence found in your profile "
                    f"had low confidence ({confidence:.2f}). Consider adding more details or projects to "
                    f"reinforce this skill."
                ),
                severity=gap_severity(requirement_type, "missing"),
                supporting=items,
            ))
        elif bucket == "partial":
            explanation = (
                f"Mentioned in your {labels[0]} but lacks substantial backing."
                if len(labels) == 1
                else f"Mentioned in {len(labels)} source(s) but lacks substantial backing."
            )
            partial.append(PartialSkill(
                skill=canonical, confidence=confidence,
                reason=f"Mentioned in {len(labels)} source(s) but lacks substantial evidence.",
                explanation=explanation, severity=gap_severity(requirement_type, "partial"),
                supporting=items,
                raw_confidence=entry["raw_confidence"], confidence_flags=entry["confidence_flags"],
            ))
        else:
            explanation = (
                f"Multiple independent sources verified {name} usage."
                if len(labels) > 1 else f"Verified in your {labels[0]}."
            )
            have.append(HaveSkill(
                skill=canonical, confidence=confidence, supporting=items,
                explanation=explanation,
                raw_confidence=entry["raw_confidence"], confidence_flags=entry["confidence_flags"],
            ))

    return have, partial, missing