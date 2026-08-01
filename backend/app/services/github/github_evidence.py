"""Writes GitHub-derived SkillEvidence rows so verified, committed code
counts toward skill confidence.

Re-derived on every sync (existing rows deleted, then rebuilt).
Non-contributed forks are excluded.

FIX #3 (depth-weighted evidence) + cross-user evidence-leak fix: every
GitHub-sourced SkillEvidence row is now both depth-weighted AND
explicitly stamped with user_id at write time.
"""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import SkillEvidence
from app.services.resume.confidence import WEIGHTS
from app.services.resume.skill_classifier import resolve_skills
from app.services.user_helpers import get_or_create_skill

GITHUB_EVIDENCE_SOURCE_TYPE = "github_repo"

DEPTH_WEIGHT_MIN_MULTIPLIER = 0.6
DEPTH_WEIGHT_MAX_MULTIPLIER = 1.3


def _depth_multiplier(depth_score: float | None) -> float:
    if depth_score is None:
        return DEPTH_WEIGHT_MIN_MULTIPLIER
    depth_score = max(0.0, min(100.0, depth_score))
    span = DEPTH_WEIGHT_MAX_MULTIPLIER - DEPTH_WEIGHT_MIN_MULTIPLIER
    return DEPTH_WEIGHT_MIN_MULTIPLIER + (depth_score / 100.0) * span


async def sync_github_skill_evidence(
    db: AsyncSession, user, technology_depth: dict[str, dict] | None = None
) -> dict:
    technology_depth = technology_depth or {}

    analysis_result = await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user.id)
    )
    all_analyses = list(analysis_result.scalars().all())

    all_analysis_ids = [a.id for a in all_analyses]
    if all_analysis_ids:
        await db.execute(
            delete(SkillEvidence)
            .where(SkillEvidence.source_type == GITHUB_EVIDENCE_SOURCE_TYPE)
            .where(SkillEvidence.source_id.in_(all_analysis_ids))
            .where(SkillEvidence.user_id == user.id)
        )

    eligible = [
        a for a in all_analyses
        if not (a.is_fork and not a.is_meaningful_fork_contribution)
    ]

    raw_tech_strings: set[str] = set()
    for a in eligible:
        raw_tech_strings.update(a.technologies or [])

    if not raw_tech_strings:
        await db.flush()
        return {"skills_evidenced": 0, "repos_considered": len(eligible)}

    resolved = await resolve_skills(raw_tech_strings, db)

    evidenced_skills: set[str] = set()
    for a in eligible:
        for raw_tech in (a.technologies or []):
            canonical = resolved.get(raw_tech)
            if canonical is None:
                continue
            skill = await get_or_create_skill(db, canonical, raw_tech)

            depth_entry = technology_depth.get(raw_tech)
            depth_score = depth_entry.get("score") if depth_entry else None
            weight = WEIGHTS["github"] * _depth_multiplier(depth_score)

            db.add(SkillEvidence(
                user_id=user.id,
                skill_id=skill.id,
                source_type=GITHUB_EVIDENCE_SOURCE_TYPE,
                source_id=a.id,
                weight=weight,
            ))
            evidenced_skills.add(canonical)

    await db.flush()
    return {"skills_evidenced": len(evidenced_skills), "repos_considered": len(eligible)}