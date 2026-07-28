# backend/app/services/resume/analysis/coverage.py
"""Compares what's evidenced across GitHub/LeetCode/Certificates against
what actually made it into the resume text. Deterministic set-difference —
no LLM needed, the data already exists in three separate tables.
"""
import uuid
from sqlalchemy import select
from app.models.facts import Experience, Project, GithubSnapshot, LeetcodeSnapshot, Certificate
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.services.resume.skill_classifier import resolve_skills

async def analyze_cross_source_coverage(db, user_id: uuid.UUID, resume_id: uuid.UUID) -> dict:
    # ── 1. Skills on the CURRENT resume ─────────────────────────────────────
    resume_skills = set()
    
    # Skills from experiences linked to latest resume
    resume_exp_skills = await db.execute(
        select(Skill.canonical_name)
        .join(SkillEvidence, SkillEvidence.skill_id == Skill.id)
        .join(Experience, (SkillEvidence.source_id == Experience.id) & (SkillEvidence.source_type == "experience"))
        .where(Experience.user_id == user_id, Experience.resume_id == resume_id)
        .distinct()
    )
    resume_skills.update(r[0] for r in resume_exp_skills.fetchall() if r[0])

    # Skills from projects linked to latest resume
    resume_proj_skills = await db.execute(
        select(Skill.canonical_name)
        .join(SkillEvidence, SkillEvidence.skill_id == Skill.id)
        .join(Project, (SkillEvidence.source_id == Project.id) & (SkillEvidence.source_type == "project"))
        .where(Project.user_id == user_id, Project.resume_id == resume_id)
        .distinct()
    )
    resume_skills.update(r[0] for r in resume_proj_skills.fetchall() if r[0])

    # ── 2. GitHub skills ────────────────────────────────────────────────────
    github_techs_result = await db.execute(
        select(GithubProjectAnalysis.technologies)
        .where(GithubProjectAnalysis.user_id == user_id)
    )
    github_techs = set()
    for row in github_techs_result.fetchall():
        if row[0]:
            github_techs.update(row[0])
            
    github_skills = set()
    if github_techs:
        resolved_gh = await resolve_skills(github_techs, db)
        github_skills = {val for val in resolved_gh.values() if val is not None}

    # ── 3. LeetCode skills ──────────────────────────────────────────────────
    leetcode_skills_result = await db.execute(
        select(Skill.canonical_name)
        .join(LeetcodeSnapshot, (LeetcodeSnapshot.tag == Skill.name) | (LeetcodeSnapshot.tag == Skill.canonical_name))
        .where(LeetcodeSnapshot.user_id == user_id)
        .distinct()
    )
    leetcode_skills = {r[0] for r in leetcode_skills_result.fetchall() if r[0]}

    # ── 4. Certificate skills ───────────────────────────────────────────────
    cert_skills_result = await db.execute(
        select(Certificate.skills)
        .where(Certificate.user_id == user_id)
    )
    all_cert_skills = set()
    for row in cert_skills_result.fetchall():
        if row[0]:
            all_cert_skills.update(row[0])
            
    cert_skills = set()
    if all_cert_skills:
        resolved_certs = await resolve_skills(all_cert_skills, db)
        cert_skills = {val for val in resolved_certs.values() if val is not None}

    # ── Set difference ──────────────────────────────────────────────────────
    github_only = github_skills - resume_skills
    leetcode_only = leetcode_skills - resume_skills
    cert_only = cert_skills - resume_skills

    return {
        "github_not_on_resume": sorted(github_only),
        "leetcode_not_on_resume": sorted(leetcode_only),
        "certificates_not_on_resume": sorted(cert_only),
    }
