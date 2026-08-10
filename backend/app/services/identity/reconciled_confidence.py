# backend/app/services/identity/reconciled_confidence.py
"""Single, shared, UNBOUNDED reconciled-confidence map — canonical skill
-> {confidence, raw_confidence, confidence_flags, sources, corroboration_count}.

This is the fix for the Skill Gap Analyzer / Engineering Identity
disagreement: Identity's top_skills applies reconcile_skill_confidence()
(claim-risk + timeline-plausibility discounting) but only to the top
MAX_TOP_SKILLS-by-confidence subset. A missing skill, by definition,
will almost never be in that top-N slice, so the Skill Gap Analyzer
cannot diff against top_skills directly — it needs the SAME
reconciliation applied to the FULL skill universe. This module is that
one shared, unbounded computation; both identity_builder.py (which
takes the top N of this for top_skills) and skill_gap/comparison.py
(which needs the full set) call this rather than each recomputing
evidence/decay/reconciliation independently.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Project, Resume
from app.models.inference import ProjectClaimAuditReview, SkillEvidence
from app.models.structure import Skill
from app.services.evidence import build_evidence_details, get_all_skill_confidences
from app.services.identity.confidence_reconciliation import reconcile_skill_confidence
from app.services.resume.confidence import compute_corroboration_count
from app.services.resume.timeline_plausibility import build_timeline_plausibility_notes


async def get_claim_risk_details(db: AsyncSession, user_id) -> list[dict]:
    """Real, unresolved (high/medium) Claim Audit findings, one entry per
    flagged project — each carries "unsupported_claims" so a consumer can
    tell WHICH skill(s) a given finding implicates. Made public and
    relocated here from identity_builder.py's private
    _get_claim_risk_details so it has exactly one owner, callable by both
    Engineering Identity and the Skill Gap Analyzer.
    """
    proj_result = await db.execute(select(Project.id, Project.name).where(Project.user_id == user_id))
    projects_by_id = {pid: name for pid, name in proj_result.all()}
    if not projects_by_id:
        return []
    audit_result = await db.execute(
        select(ProjectClaimAuditReview).where(ProjectClaimAuditReview.project_id.in_(projects_by_id.keys()))
    )
    details: list[dict] = []
    for row in audit_result.scalars().all():
        report_json = row.report_json or {}
        narrative = report_json.get("narrative", {})
        facts = report_json.get("facts", {})
        level = narrative.get("risk_level", "low")
        if level in ("high", "medium"):
            details.append({
                "project": projects_by_id.get(row.project_id, "Unknown project"),
                "risk_level": level,
                "headline": narrative.get("headline", ""),
                "unsupported_claims": facts.get("unsupported_claims", []),
            })
    return details


async def _get_latest_resume_id(db: AsyncSession, user_id):
    result = await db.execute(
        select(Resume.id).where(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def get_reconciled_skill_confidences(db: AsyncSession, user_id) -> dict[str, dict]:
    """canonical -> {"skill": str, "confidence": float, "raw_confidence": float,
    "confidence_flags": list[str], "sources": list[str],
    "corroboration_count": int}. UNBOUNDED — every skill with real
    evidence for this user, not just the top-N. This is the one place
    claim-risk / timeline-plausibility reconciliation is computed;
    identity_builder.build_identity_facts() (top-N slice for top_skills)
    and skill_gap/comparison.py (needs the full set, since a missing
    skill by definition won't be in a top-N-by-confidence list) both
    call this rather than each recomputing reconciliation independently.
    """
    confidences = await get_all_skill_confidences(db, user_id)
    if not confidences:
        return {}

    canonical_names = list(confidences.keys())
    skill_rows = await db.execute(select(Skill).where(Skill.canonical_name.in_(canonical_names)))
    skills_by_canonical = {s.canonical_name: s for s in skill_rows.scalars().all()}

    # N+1 avoidance — same pattern identity_builder._get_top_skills()
    # already used: one batched evidence query over every skill id.
    skill_ids = [s.id for s in skills_by_canonical.values()]
    evidence_by_skill_id: dict = {}
    if skill_ids:
        ev_result = await db.execute(
            select(SkillEvidence).where(
                SkillEvidence.skill_id.in_(skill_ids),
                SkillEvidence.user_id == user_id,
            )
        )
        for row in ev_result.scalars().all():
            evidence_by_skill_id.setdefault(row.skill_id, []).append(row)

    base_entries: list[dict] = []
    for canonical, confidence in confidences.items():
        skill = skills_by_canonical.get(canonical)
        sources: list[str] = []
        corroboration_count = 0
        if skill is not None:
            evidence_rows = evidence_by_skill_id.get(skill.id, [])
            sources = await build_evidence_details(db, evidence_rows)
            corroboration_count = compute_corroboration_count(evidence_rows)
        base_entries.append({
            "skill": canonical,
            "confidence": round(confidence, 2),
            "sources": sources,
            "corroboration_count": corroboration_count,
        })

    claim_risk_details = await get_claim_risk_details(db, user_id)

    resume_id = await _get_latest_resume_id(db, user_id)
    timeline_notes = await build_timeline_plausibility_notes(db, user_id, resume_id) if resume_id else []

    reconciled = reconcile_skill_confidence(base_entries, claim_risk_details, timeline_notes)

    return {entry["skill"]: entry for entry in reconciled}