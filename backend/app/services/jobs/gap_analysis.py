from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Experience, JobDescription, Project
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.schemas.skill_gap import HaveSkill, MissingSkill, PartialSkill, SkillGapReport
from app.services.jobs.effort_estimation import estimate_weeks
from app.services.jobs.prioritization import PrioritizationError, prioritize_missing_skills
from app.services.jobs.skill_categories import get_curriculum_phase, get_curriculum_rank
from app.services.resume.confidence import compute_skill_confidence
from app.services.resume.review import classify_match
from app.services.evidence import build_evidence_details

async def _historical_skill_frequency(db: AsyncSession, user_id) -> Counter:
    """How often each canonical skill has shown up as a requirement across
    every JD this user has ever pasted. Purely a priority-ordering signal
    for the fallback path below — a skill that keeps reappearing across
    applications is worth tackling before one that showed up once.
    """
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


def _fallback_prioritization(
    missing_skill_names: list[str], frequency: Counter, canonical_order: list[str]
) -> tuple[list[str], dict[str, int]]:
    """Deterministic fallback used when the contextual-reasoning LLM call
    fails — frequency across past JDs, then original JD order, plus a flat
    per-skill estimate. Same graceful-degradation philosophy as the LeetCode
    manual-form fallback: never let an unofficial/best-effort call crash the
    whole report.
    """
    ordered = sorted(
        missing_skill_names,
        key=lambda s: (get_curriculum_rank(s), -frequency.get(s, 0), canonical_order.index(s)),
    )
    weeks = {s: estimate_weeks(1) for s in ordered}
    return ordered, weeks


async def analyze_skill_gap(
    db: AsyncSession,
    user_id,
    canonical_skills: dict[str, str],  # canonical_name -> "required" | "implicit" | "nice_to_have"
    architecture_topics: list[str],
    role: str | None,
    company: str | None,
) -> SkillGapReport:
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
            missing.append(
                MissingSkill(
                    skill=canonical,
                    reason="No evidence found in profile",
                    unmatched_explanation=(
                        f"{canonical.title()} wasn't matched because no verified evidence was found in your: "
                        f"Resume, Projects, or GitHub. If you've used {canonical.title()}, "
                        f"add it to one of those sources and resync."
                    ),
                )
            )
            continue

        evidence_result = await db.execute(select(SkillEvidence).where(SkillEvidence.skill_id == skill.id))
        evidence_rows = list(evidence_result.scalars().all())

        if not evidence_rows:
            missing.append(
                MissingSkill(
                    skill=canonical,
                    reason="No evidence found in profile",
                    unmatched_explanation=(
                        f"{canonical.title()} wasn't matched because no verified evidence was found in your: "
                        f"Resume, Projects, or GitHub. If you've used {canonical.title()}, "
                        f"add it to one of those sources and resync."
                    ),
                )
            )
            continue

        confidence = compute_skill_confidence([e.weight for e in evidence_rows])
        bucket = classify_match(confidence)

        if bucket == "missing":
            missing.append(
                MissingSkill(
                    skill=canonical,
                    reason=f"Low confidence ({confidence:.2f}) — insufficient evidence",
                    unmatched_explanation=(
                        f"{canonical.title()} wasn't matched because the verified evidence found in your profile had low confidence ({confidence:.2f}). "
                        f"Consider adding more details or projects to reinforce this skill."
                    ),
                )
            )
            continue

        evidence_details = await build_evidence_details(db, evidence_rows)

        if bucket == "partial":
            if len(evidence_details) == 1:
                explanation = f"Mentioned in your {evidence_details[0]} but lacks substantial backing."
            else:
                explanation = f"Mentioned in {len(evidence_details)} source(s) but lacks substantial backing."
            partial.append(
                PartialSkill(
                    skill=canonical,
                    confidence=confidence,
                    reason=f"Mentioned in {len(evidence_details)} source(s) but lacks substantial evidence.",
                    explanation=explanation,
                )
            )
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
        try:
            # Sort missing list by curriculum rank to group them by dependency
            curriculum_ordered_missing = sorted(missing_names, key=get_curriculum_rank)
            learning_plan_curriculum = [
                {
                    "skill": s,
                    "weeks": estimate_weeks(1),
                    "phase": get_curriculum_phase(s),
                }
                for s in curriculum_ordered_missing
            ]

            context = {
                "role": role,
                "company": company,
                "required_skills": [s for s, t in canonical_skills.items() if t == "required"],
                "implicit_skills": [s for s, t in canonical_skills.items() if t == "implicit"],
                "architecture_topics": architecture_topics,
                "nice_to_have": [s for s, t in canonical_skills.items() if t == "nice_to_have"],
                "have": [{"skill": h.skill, "confidence": h.confidence} for h in have],
                "partial": [{"skill": p.skill, "confidence": p.confidence} for p in partial],
                "missing": missing_names,
                "learning_plan_curriculum": learning_plan_curriculum,
            }
            result = await prioritize_missing_skills(context)

            # Validate: never trust the LLM's list blindly. Drop anything
            # hallucinated, and make sure every real missing skill is present
            # even if the LLM dropped one.
            valid_priority = [s for s in result.priority_order if s in missing_names]
            for s in missing_names:
                if s not in valid_priority:
                    valid_priority.append(s)

            # Force re-sort of priority by curriculum rank
            valid_priority = sorted(valid_priority, key=get_curriculum_rank)

            weeks_by_skill = {
                s: max(1, result.estimated_weeks.get(s, estimate_weeks(1))) for s in missing_names
            }
        except PrioritizationError as e:
            print(f"[TRACING] Prioritization degraded, using fallback ordering: {e}", flush=True)
            valid_priority, weeks_by_skill = _fallback_prioritization(missing_names, frequency, canonical_order)
    else:
        valid_priority, weeks_by_skill = [], {}

    for m in missing:
        m.estimated_weeks = weeks_by_skill.get(m.skill, 0)

    # Force re-sort of missing report by curriculum rank
    missing.sort(key=lambda m: get_curriculum_rank(m.skill))
    total_weeks = sum(weeks_by_skill.values()) if weeks_by_skill else estimate_weeks(len(missing))

    return SkillGapReport(
        have=have,
        partial=partial,
        missing=missing,
        priority_order=valid_priority,
        estimated_weeks=total_weeks,
    )