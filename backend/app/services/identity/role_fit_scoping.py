"""Builds scope-filtered skill-evidence lists for get_role_fit(), so every
caller passes the SAME shape (canonical decayed confidence + real
sources) filtered to a different SkillEvidence source_type set, instead
of each reimplementing its own skill-set construction (Engineering
Identity fix #2).

FIX (cross-user evidence leak): `user_id` is now a REQUIRED parameter.
This was the exact function flagged as pooling every user's evidence
together — every caller (identity_builder.py, resume/analysis/engine.py,
api/resume.py, github_reviewer.py) has been updated to pass it.
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
    db: AsyncSession, user_id, source_types: set[str] | None = None
) -> list[dict]:
    """source_types=None means "all sources for this user" — NOT "all
    users." user_id is always required.
    """
    skill_result = await db.execute(select(Skill))
    skills = skill_result.scalars().all()

    out: list[dict] = []
    for skill in skills:
        ev_result = await db.execute(
            select(SkillEvidence).where(
                SkillEvidence.skill_id == skill.id,
                SkillEvidence.user_id == user_id,
            )
        )
        rows = list(ev_result.scalars().all())
        if source_types is not None:
            rows = [r for r in rows if r.source_type in source_types]
        if not rows:
            continue
        confidence = compute_decayed_skill_confidence(rows)
        sources = await build_evidence_details(db, rows)
        out.append({"skill": skill.canonical_name, "confidence": round(confidence, 2), "sources": sources})
    return out