"""Builds scope-filtered skill-evidence lists for get_role_fit(), so every
caller passes the SAME shape (canonical decayed confidence + real
sources) filtered to a different SkillEvidence source_type set, instead
of each reimplementing its own skill-set construction (fix #2).

KNOWN PRE-EXISTING LIMITATION (not introduced by this fix, not in scope
to fix here): SkillEvidence has no user_id column — the same limitation
already present in services/evidence.py's get_all_skill_confidences and
career_planner/context_builder.py's _get_skills_by_confidence. This
module mirrors that existing (imperfect but consistent) behavior rather
than inventing new, inconsistent scoping logic.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.services.evidence import build_evidence_details
from app.services.resume.confidence import compute_decayed_skill_confidence

RESUME_SOURCE_TYPES = {"project", "experience"}
GITHUB_SOURCE_TYPES = {"github_repo"}


async def build_scoped_skill_evidence(
    db: AsyncSession, source_types: set[str] | None = None
) -> list[dict]:
    """source_types=None means "all sources" (no filtering)."""
    skill_result = await db.execute(select(Skill))
    skills = skill_result.scalars().all()

    out: list[dict] = []
    for skill in skills:
        ev_result = await db.execute(select(SkillEvidence).where(SkillEvidence.skill_id == skill.id))
        rows = list(ev_result.scalars().all())
        if source_types is not None:
            rows = [r for r in rows if r.source_type in source_types]
        if not rows:
            continue
        confidence = compute_decayed_skill_confidence(rows)
        sources = await build_evidence_details(db, rows)
        out.append({"skill": skill.canonical_name, "confidence": round(confidence, 2), "sources": sources})
    return out