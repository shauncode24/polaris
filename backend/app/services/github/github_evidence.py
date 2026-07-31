"""Writes GitHub-derived SkillEvidence rows so verified, committed code
counts toward skill confidence.

Before this module existed, GitHub sync updated GithubProjectAnalysis
(and wrote a ProfileSnapshot) but never touched SkillEvidence at all —
the confidence formula that drives Skill Gap Analyzer, Career Planner,
and the Interview Response Agent (resume/confidence.py's WEIGHTS) was
computed entirely from self-reported resume data plus LeetCode tags.
The one source that's hardest to fake — actual committed, timestamped
code — was structurally excluded from the number that matters most.

Re-derived on every sync (existing rows deleted, then rebuilt) so this
never accumulates stale evidence as repos/technologies change, mirroring
the delete-then-reinsert pattern resume/ingestion.py's
sync_resume_skills_deterministically already uses for the same reason.

Non-contributed forks are excluded — a forked repo with no real
original work isn't evidence of this user's skill, same rule already
applied throughout github_insights.py / github_knowledge.py.
"""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import SkillEvidence
from app.services.resume.confidence import WEIGHTS
from app.services.resume.skill_classifier import resolve_skills
from app.services.user_helpers import get_or_create_skill

GITHUB_EVIDENCE_SOURCE_TYPE = "github_repo"


async def sync_github_skill_evidence(db: AsyncSession, user) -> dict:
    """Rebuilds this user's GitHub-sourced SkillEvidence rows from the
    GithubProjectAnalysis rows that were just upserted by sync_github().
    Must be called AFTER those upserts are flushed but before the sync's
    final commit, so it sees this sync's latest per-repo technology data.
    """
    analysis_result = await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user.id)
    )
    all_analyses = list(analysis_result.scalars().all())

    # Always clear ALL of this user's existing github_repo evidence first —
    # not just for eligible repos — so a repo that becomes a non-contributed
    # fork, gets archived-and-emptied, or is removed entirely doesn't leave
    # stale evidence behind.
    all_analysis_ids = [a.id for a in all_analyses]
    if all_analysis_ids:
        await db.execute(
            delete(SkillEvidence)
            .where(SkillEvidence.source_type == GITHUB_EVIDENCE_SOURCE_TYPE)
            .where(SkillEvidence.source_id.in_(all_analysis_ids))
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
            db.add(SkillEvidence(
                skill_id=skill.id,
                source_type=GITHUB_EVIDENCE_SOURCE_TYPE,
                source_id=a.id,
                weight=WEIGHTS["github"],
            ))
            evidenced_skills.add(canonical)

    await db.flush()
    return {"skills_evidenced": len(evidenced_skills), "repos_considered": len(eligible)}