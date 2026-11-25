"""Reads a user's skill evidence and turns it into confidence.

  get_all_skill_confidences          canonical skill -> decayed confidence
  get_reconciled_skill_confidences   the same, after claim-risk and
                                     timeline discounts, with sources
  build_evidence_details             human-readable source labels
  get_claim_risk_details             unresolved claim-audit findings

get_reconciled_skill_confidences is the one place the claim-risk and
timeline discounts are applied, and covers EVERY skill with evidence
(not a top-N slice). Engineering Identity, the skill-gap analysis, the
career planner and the interview context all read it, so they cannot
disagree about how confident a skill is.

Skills the user has hidden (UserSkillOverride) are excluded from every
reader here.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Experience, Project, Resume, UserSkillOverride
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import ProjectClaimAuditReview, SkillEvidence
from app.models.structure import Skill
from app.services.evidence.reconciliation import reconcile_skill_confidence
from app.services.evidence.scoring import compute_corroboration_count, compute_decayed_skill_confidence
from app.services.resume.timeline_plausibility import build_timeline_plausibility_notes


async def build_evidence_details(db: AsyncSession, evidence_rows: list[SkillEvidence]) -> list[str]:
    """Human-readable evidence trail for a list of SkillEvidence rows.
    Unchanged by the user-scoping fix — it operates on rows already
    handed to it by a caller, and never queries SkillEvidence itself.

    Phase 4: added a "linkedin_profile" branch so LinkedIn-sourced
    evidence gets a real, visible provenance label instead of silently
    contributing to confidence math with no corresponding detail string
    (previously the only source_type that fell through every branch).
    """
    project_ids = [e.source_id for e in evidence_rows if e.source_type == "project" and e.source_id]
    experience_ids = [e.source_id for e in evidence_rows if e.source_type == "experience" and e.source_id]
    github_repo_ids = [e.source_id for e in evidence_rows if e.source_type == "github_repo" and e.source_id]

    projects: dict = {}
    if project_ids:
        result = await db.execute(select(Project).where(Project.id.in_(project_ids)))
        projects = {p.id: p for p in result.scalars().all()}

    experiences: dict = {}
    if experience_ids:
        result = await db.execute(select(Experience).where(Experience.id.in_(experience_ids)))
        experiences = {e.id: e for e in result.scalars().all()}

    github_repos: dict = {}
    if github_repo_ids:
        result = await db.execute(
            select(GithubProjectAnalysis).where(GithubProjectAnalysis.id.in_(github_repo_ids))
        )
        github_repos = {r.id: r for r in result.scalars().all()}

    details: list[str] = []
    for e in evidence_rows:
        if e.source_type == "project" and e.source_id in projects:
            details.append(f"Project: {projects[e.source_id].name}")
        elif e.source_type == "experience" and e.source_id in experiences:
            exp = experiences[e.source_id]
            details.append(f"Experience: {exp.role} at {exp.company}")
        elif e.source_type == "github_repo" and e.source_id in github_repos:
            details.append(f"GitHub: {github_repos[e.source_id].repo_name}")
        elif e.source_type == "leetcode_tag":
            details.append("LeetCode practice history")
        elif e.source_type == "certificate":
            details.append("Certificate")
        elif e.source_type == "linkedin_profile":
            details.append("LinkedIn profile")
    return list(dict.fromkeys(details))


async def get_all_skill_confidences(db: AsyncSession, user_id) -> dict[str, float]:
    """canonical_name -> recency-decayed confidence, for ONE user.

    One query over that user's evidence, grouped in Python. Skills the user
    has hidden are left out.
    """
    hidden = select(UserSkillOverride.skill_id).where(
        UserSkillOverride.user_id == user_id, UserSkillOverride.is_hidden.is_(True)
    )
    result = await db.execute(
        select(Skill.canonical_name, SkillEvidence)
        .join(SkillEvidence, SkillEvidence.skill_id == Skill.id)
        .where(SkillEvidence.user_id == user_id)
        .where(Skill.id.not_in(hidden))
    )
    evidence_by_skill: dict[str, list[SkillEvidence]] = {}
    for canonical_name, evidence_row in result.all():
        evidence_by_skill.setdefault(canonical_name, []).append(evidence_row)
    return {
        canonical: compute_decayed_skill_confidence(rows) for canonical, rows in evidence_by_skill.items()
    }


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