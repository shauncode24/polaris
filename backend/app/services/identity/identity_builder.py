"""Builds the deterministic IdentityFacts object — the ONLY input the
Engineering Identity synthesis LLM call (identity_synthesizer.py) is
allowed to reason over. Pulls from every module that already computes
real, verified facts: Resume Analysis Engine, the unified skill
evidence pool, GitHub knowledge (including architecture_maturity and
technology_depth), LeetCode knowledge, cross-source coverage gaps,
timeline plausibility, active goals, and recent job-match history.

This is the "review item 10" fix: previously six-plus independent LLM
narrators (Resume Reviewer, Coherence, Tailoring, JD Interpretation,
GitHub Portfolio Review, LeetCode Portfolio Review) each generated their
own opinion of the same person from a partial view of the evidence,
with nothing reconciling them. This builder is step one — gathering ONE
complete, deterministic fact base. identity_synthesizer.py is step two
— exactly one LLM pass over it.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import JobDescription, Resume, Project
from app.models.goals import Goal
from app.models.inference import ResumeAnalysis, SkillEvidence, ProjectClaimAuditReview
from app.models.structure import Skill
from app.schemas.engineering_identity import IdentityFacts
from app.services.evidence import build_evidence_details, get_all_skill_confidences
from app.services.github.github_knowledge import build_github_knowledge_object
from app.services.leetcode.leetcode_knowledge import build_leetcode_knowledge_object
from app.services.resume.analysis.coverage import analyze_cross_source_coverage
from app.services.resume.analysis.role_fit import (
    compute_combined_role_fit,
    get_confident_canonical_skills,
)

MAX_TOP_SKILLS = 10
MAX_TECH_DEPTH_HIGHLIGHTS = 6
MAX_RECENT_JOB_MATCHES = 3


async def _get_top_skills(db: AsyncSession, limit: int = MAX_TOP_SKILLS) -> list[dict]:
    confidences = await get_all_skill_confidences(db)
    if not confidences:
        return []

    ranked = sorted(confidences.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    canonical_names = [c for c, _ in ranked]

    skill_rows = await db.execute(select(Skill).where(Skill.canonical_name.in_(canonical_names)))
    skills_by_canonical = {s.canonical_name: s for s in skill_rows.scalars().all()}

    out = []
    for canonical, confidence in ranked:
        skill = skills_by_canonical.get(canonical)
        sources: list[str] = []
        if skill is not None:
            ev_result = await db.execute(select(SkillEvidence).where(SkillEvidence.skill_id == skill.id))
            evidence_rows = list(ev_result.scalars().all())
            sources = await build_evidence_details(db, evidence_rows)
        out.append({"skill": canonical, "confidence": round(confidence, 2), "sources": sources})
    return out


async def _get_latest_resume(db: AsyncSession, user_id) -> Resume | None:
    result = await db.execute(
        select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def _get_latest_resume_analysis(db: AsyncSession, user_id) -> dict | None:
    result = await db.execute(
        select(ResumeAnalysis)
        .where(ResumeAnalysis.user_id == user_id)
        .order_by(ResumeAnalysis.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row.analysis_json if row else None


async def _get_active_goals(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(
        select(Goal)
        .where(Goal.user_id == user_id)
        .where(Goal.status_pct < 100.0)
        .order_by(Goal.deadline.asc().nullslast())
    )
    return [
        {
            "title": g.title,
            "deadline": g.deadline.isoformat() if g.deadline else None,
            "priority": g.priority,
            "status_pct": g.status_pct,
        }
        for g in result.scalars().all()
    ]


async def _get_recent_job_matches(db: AsyncSession, user_id, limit: int = MAX_RECENT_JOB_MATCHES) -> list[dict]:
    result = await db.execute(
        select(JobDescription)
        .where(JobDescription.user_id == user_id)
        .where(JobDescription.analysis_result.isnot(None))
        .order_by(JobDescription.created_at.desc())
        .limit(limit)
    )
    out = []
    for jd in result.scalars().all():
        overall = (jd.analysis_result or {}).get("overall_match", {})
        out.append({
            "role": jd.role,
            "company": jd.company,
            "match_percentage": overall.get("percentage"),
            "match_label": overall.get("label"),
        })
    return out


async def _get_claim_risk_summary(db: AsyncSession, user_id) -> dict:
    proj_result = await db.execute(select(Project.id).where(Project.user_id == user_id))
    project_ids = [r[0] for r in proj_result.all()]
    if not project_ids:
        return {"high_risk_count": 0, "medium_risk_count": 0}
    audit_result = await db.execute(
        select(ProjectClaimAuditReview).where(ProjectClaimAuditReview.project_id.in_(project_ids))
    )
    high = medium = 0
    for row in audit_result.scalars().all():
        level = ((row.report_json or {}).get("narrative", {})).get("risk_level")
        if level == "high":
            high += 1
        elif level == "medium":
            medium += 1
    return {"high_risk_count": high, "medium_risk_count": medium}


async def build_identity_facts(db: AsyncSession, user_id) -> IdentityFacts:
    top_skills = await _get_top_skills(db)

    confident_skills = await get_confident_canonical_skills(db)
    role_fit = compute_combined_role_fit(confident_skills)

    resume_analysis = await _get_latest_resume_analysis(db, user_id)
    resume_score = resume_analysis.get("overall_score") if resume_analysis else None
    resume_grade = resume_analysis.get("grade") if resume_analysis else None

    github_knowledge = await build_github_knowledge_object(db, user_id) or {}
    github_summary = github_knowledge.get("summary", {})
    architecture_maturity = github_knowledge.get("architecture_maturity", {})

    technology_depth = github_knowledge.get("technology_depth", {})
    technology_depth_highlights = sorted(
        [{"technology": tech, **data} for tech, data in technology_depth.items()],
        key=lambda d: d.get("score", 0),
        reverse=True,
    )[:MAX_TECH_DEPTH_HIGHLIGHTS]

    leetcode_knowledge = await build_leetcode_knowledge_object(db, user_id) or {}
    leetcode_summary = leetcode_knowledge.get("leetcode_summary", {})
    leetcode_topic_mastery = leetcode_knowledge.get("topic_mastery", [])

    latest_resume = await _get_latest_resume(db, user_id)
    coverage_gaps: dict = {}
    timeline_plausibility_notes: list[dict] = []
    if latest_resume is not None:
        coverage_gaps = await analyze_cross_source_coverage(db, user_id, latest_resume.id)
        timeline_plausibility_notes = coverage_gaps.get("timeline_plausibility_notes", [])

    active_goals = await _get_active_goals(db, user_id)
    recent_job_matches = await _get_recent_job_matches(db, user_id)

    return IdentityFacts(
        top_skills=top_skills,
        role_fit=role_fit,
        resume_score=resume_score,
        resume_grade=resume_grade,
        github_summary=github_summary,
        architecture_maturity=architecture_maturity,
        technology_depth_highlights=technology_depth_highlights,
        leetcode_summary=leetcode_summary,
        leetcode_topic_mastery=leetcode_topic_mastery,
        coverage_gaps={k: v for k, v in coverage_gaps.items() if k != "timeline_plausibility_notes"},
        timeline_plausibility_notes=timeline_plausibility_notes,
        active_goals=active_goals,
        recent_job_matches=recent_job_matches,
        claim_risk_summary=await _get_claim_risk_summary(db, user_id),
    )