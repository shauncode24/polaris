# backend/app/services/skill_gap/comparison.py
"""Core have/partial/missing loop — moved from jobs/gap_analysis.py.
Now takes a JobIntelligenceProfile instead of a raw canonical_skills
dict + architecture_topics list; the role-intrinsic priority ordering
(band boundaries) is derived here from the profile's own
requirement_type + curriculum_phase, then handed to the narrowed
prioritize_missing_skills() as a given, per design doc §5.4.
"""
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import JobDescription
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.schemas.skill_gap.skill_gap import HaveSkill, MissingSkill, PartialSkill, SkillGapReport
from app.services.evidence import build_evidence_details
from app.services.resume.confidence import compute_decayed_skill_confidence
from app.services.resume.review import classify_match
from app.services.skill_gap.effort_estimation import estimate_weeks
from app.services.skill_gap.prioritization import PrioritizationError, prioritize_missing_skills
from app.services.taxonomy.skill_taxonomy import get_curriculum_rank

_BAND_ORDER = {"required": 0, "implicit": 1, "nice_to_have": 2}


async def _historical_skill_frequency(db: AsyncSession, user_id) -> Counter:
    result = await db.execute(
        select(JobDescription.extracted_requirements).where(JobDescription.user_id == user_id)
    )
    counter: Counter = Counter()
    for (requirements,) in result.all():
        if not requirements:
            continue
        for skill in requirements.get("resolved_skills", []):
            counter[skill] += 1
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
        return SkillGapReport(have=[], partial=[], missing=[], priority_order=[], estimated_weeks=0)

    canonical_order = list(canonical_skills.keys())
    skill_rows = await db.execute(select(Skill).where(Skill.canonical_name.in_(canonical_order)))
    skills_by_canonical = {s.canonical_name: s for s in skill_rows.scalars().all()}

    have: list[HaveSkill] = []
    partial: list[PartialSkill] = []
    missing: list[MissingSkill] = []

    for canonical in canonical_order:
        skill = skills_by_canonical.get(canonical)
        if skill is None:
            missing.append(MissingSkill(
                skill=canonical,
                reason="No evidence found in profile",
                unmatched_explanation=(
                    f"{canonical.title()} wasn't matched because no verified evidence was found in your: "
                    f"Resume, Projects, or GitHub. If you've used {canonical.title()}, "
                    f"add it to one of those sources and resync."
                ),
            ))
            continue

        evidence_result = await db.execute(
            select(SkillEvidence).where(
                SkillEvidence.skill_id == skill.id,
                SkillEvidence.user_id == user_id,
            )
        )
        evidence_rows = list(evidence_result.scalars().all())

        if not evidence_rows:
            missing.append(MissingSkill(
                skill=canonical,
                reason="No evidence found in profile",
                unmatched_explanation=(
                    f"{canonical.title()} wasn't matched because no verified evidence was found in your: "
                    f"Resume, Projects, or GitHub. If you've used {canonical.title()}, "
                    f"add it to one of those sources and resync."
                ),
            ))
            continue

        confidence = compute_decayed_skill_confidence(evidence_rows)
        bucket = classify_match(confidence)

        if bucket == "missing":
            missing.append(MissingSkill(
                skill=canonical,
                reason=f"Low confidence ({confidence:.2f}) — insufficient evidence",
                unmatched_explanation=(
                    f"{canonical.title()} wasn't matched because the verified evidence found in your profile "
                    f"had low confidence ({confidence:.2f}). Consider adding more details or projects to "
                    f"reinforce this skill."
                ),
            ))
            continue

        evidence_details = await build_evidence_details(db, evidence_rows)

        if bucket == "partial":
            explanation = (
                f"Mentioned in your {evidence_details[0]} but lacks substantial backing."
                if len(evidence_details) == 1
                else f"Mentioned in {len(evidence_details)} source(s) but lacks substantial backing."
            )
            partial.append(PartialSkill(
                skill=canonical, confidence=confidence,
                reason=f"Mentioned in {len(evidence_details)} source(s) but lacks substantial evidence.",
                explanation=explanation,
            ))
        else:
            if len(evidence_details) > 1:
                explanation = f"Multiple independent sources verified {canonical.title()} usage."
            elif len(evidence_details) == 1:
                explanation = f"Verified in your {evidence_details[0]}."
            else:
                explanation = f"Verified {canonical.title()} usage."
            have.append(HaveSkill(skill=canonical, confidence=confidence, evidence=evidence_details, explanation=explanation))

    frequency = await _historical_skill_frequency(db, user_id)
    missing_names = [m.skill for m in missing]

    if missing_names:
        role_priority_order = _role_priority_order(missing_names, canonical_skills)
        try:
            learning_plan_curriculum = [
                {"skill": s, "weeks": estimate_weeks(1), "phase": ""} for s in role_priority_order
            ]
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
            print(f"[TRACING] Prioritization degraded, using role-order fallback: {e}", flush=True)
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
    )