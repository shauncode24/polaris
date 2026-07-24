from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Experience, JobDescription, Project
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.schemas.skill_gap import HaveSkill, MissingSkill, SkillGapReport
from app.services.jobs.effort_estimation import estimate_weeks
from app.services.resume.confidence import compute_skill_confidence
from app.services.resume.review import REVIEW_THRESHOLD


async def _build_evidence_details(db: AsyncSession, evidence_rows: list[SkillEvidence]) -> list[str]:
    """SkillEvidence rows only store a weight + a source_id — the human-
    readable detail ("Cortex Route", "Backend Intern at X") lives on the
    Project/Experience row itself, so we join back to build a readable
    evidence trail instead of a bare list of weights.
    """
    project_ids = [e.source_id for e in evidence_rows if e.source_type == "project" and e.source_id]
    experience_ids = [e.source_id for e in evidence_rows if e.source_type == "experience" and e.source_id]

    projects: dict = {}
    if project_ids:
        result = await db.execute(select(Project).where(Project.id.in_(project_ids)))
        projects = {p.id: p for p in result.scalars().all()}

    experiences: dict = {}
    if experience_ids:
        result = await db.execute(select(Experience).where(Experience.id.in_(experience_ids)))
        experiences = {e.id: e for e in result.scalars().all()}

    details: list[str] = []
    for e in evidence_rows:
        if e.source_type == "project" and e.source_id in projects:
            details.append(f"Project: {projects[e.source_id].name}")
        elif e.source_type == "experience" and e.source_id in experiences:
            exp = experiences[e.source_id]
            details.append(f"Experience: {exp.role} at {exp.company}")
        elif e.source_type == "leetcode_tag":
            details.append("LeetCode practice history")
        elif e.source_type == "certificate":
            details.append("Certificate")
    return details


async def _historical_skill_frequency(db: AsyncSession, user_id) -> Counter:
    """How often each canonical skill has shown up as a requirement across
    every JD this user has ever pasted (including this one, once persisted
    by the caller). Purely a priority-ordering signal: a skill that keeps
    reappearing across applications is worth tackling before one that
    showed up once and might be a one-off.
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


async def analyze_skill_gap(
    db: AsyncSession,
    user_id,
    canonical_skills: list[str],
) -> SkillGapReport:
    """canonical_skills must already be resolved + deduplicated, in the
    JD's own original order (used as a tie-breaker below). Resolution
    itself happens once, in the API layer, so it isn't repeated here.
    """
    if not canonical_skills:
        return SkillGapReport(have=[], missing=[], priority_order=[], estimated_weeks=0)

    skill_rows = await db.execute(select(Skill).where(Skill.canonical_name.in_(canonical_skills)))
    skills_by_canonical = {s.canonical_name: s for s in skill_rows.scalars().all()}

    have: list[HaveSkill] = []
    missing: list[MissingSkill] = []

    for canonical in canonical_skills:
        skill = skills_by_canonical.get(canonical)
        if skill is None:
            missing.append(MissingSkill(skill=canonical, reason="No evidence found in profile"))
            continue

        evidence_result = await db.execute(
            select(SkillEvidence).where(SkillEvidence.skill_id == skill.id)
        )
        evidence_rows = list(evidence_result.scalars().all())

        if not evidence_rows:
            missing.append(MissingSkill(skill=canonical, reason="No evidence found in profile"))
            continue

        confidence = compute_skill_confidence([e.weight for e in evidence_rows])

        if confidence < REVIEW_THRESHOLD:
            missing.append(MissingSkill(
                skill=canonical,
                reason=f"Low confidence ({confidence:.2f}) — insufficient evidence",
            ))
            continue

        evidence_details = await _build_evidence_details(db, evidence_rows)
        have.append(HaveSkill(skill=canonical, confidence=confidence, evidence=evidence_details))

    frequency = await _historical_skill_frequency(db, user_id)
    missing.sort(key=lambda m: (-frequency.get(m.skill, 0), canonical_skills.index(m.skill)))
    priority_order = [m.skill for m in missing]

    return SkillGapReport(
        have=have,
        missing=missing,
        priority_order=priority_order,
        estimated_weeks=estimate_weeks(len(missing)),
    )