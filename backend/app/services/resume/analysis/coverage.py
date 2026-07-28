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
    EXCLUDED_LEETCODE_TAGS = {
        "array", "string", "sorting", "math", "simulation", "two pointers", 
        "matrix", "hash table", "search", "binary search", "sliding window",
        "stack", "queue", "linked list", "recursion", "divide and conquer",
        "greedy", "heap", "priority queue", "bit manipulation", "counting",
        "number theory", "combinatorics"
    }
    
    leetcode_skills_result = await db.execute(
        select(Skill.canonical_name)
        .join(LeetcodeSnapshot, (LeetcodeSnapshot.tag == Skill.name) | (LeetcodeSnapshot.tag == Skill.canonical_name))
        .where(LeetcodeSnapshot.user_id == user_id)
        .distinct()
    )
    leetcode_skills = {
        r[0] for r in leetcode_skills_result.fetchall()
        if r[0] and r[0].lower() not in EXCLUDED_LEETCODE_TAGS
    }

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

    # ── 5. Fetch GitHub project metadata to build mapping & suggestions ───
    github_projects_result = await db.execute(
        select(GithubProjectAnalysis)
        .where(GithubProjectAnalysis.user_id == user_id)
    )
    github_projects = github_projects_result.scalars().all()

    # Get names/urls of projects on the resume
    resume_projects_result = await db.execute(
        select(Project.name, Project.repo_url)
        .where(Project.user_id == user_id, Project.resume_id == resume_id)
    )
    resume_projects_data = resume_projects_result.fetchall()
    resume_project_names = {r[0].lower() for r in resume_projects_data if r[0]}
    resume_project_urls = {r[1].lower() for r in resume_projects_data if r[1]}

    # Map missing GitHub technologies to specific repo names
    github_gap_details = []
    for skill in sorted(github_only):
        matching_repos = []
        for gp in github_projects:
            if gp.technologies and any(t.lower() == skill.lower() for t in gp.technologies):
                matching_repos.append(gp.repo_name)
        if matching_repos:
            repos_str = ", ".join(matching_repos[:2])
            reason = f"Evidenced in your GitHub repo '{repos_str}' but missing from your resume."
            github_gap_details.append({
                "skill": skill,
                "reason": reason,
                "repos": matching_repos
            })
        else:
            github_gap_details.append({
                "skill": skill,
                "reason": f"Evidenced on your GitHub profile but missing from your resume.",
                "repos": []
            })

    # Suggestions for missing GitHub projects entirely (Polaris personalized recommendations)
    project_suggestions = []
    for gp in github_projects:
        is_on_resume = False
        gp_name_lower = gp.repo_name.lower()
        if gp_name_lower in resume_project_names:
            is_on_resume = True
        for url in resume_project_urls:
            if gp_name_lower in url:
                is_on_resume = True
                
        if not is_on_resume:
            techs = ", ".join(gp.technologies[:3])
            tech_desc = f" built using {techs}" if gp.technologies else ""
            
            if gp.quality_score and gp.quality_score >= 60:
                reason = f"Your high-quality repository '{gp.repo_name}'{tech_desc} (Quality: {gp.quality_score}%) is missing from your resume."
                project_suggestions.append({
                    "repo_name": gp.repo_name,
                    "technologies": gp.technologies,
                    "reason": reason,
                    "type": "project_addition"
                })
            elif gp.activity_score and gp.activity_score >= 50:
                reason = f"Your highly active repository '{gp.repo_name}'{tech_desc} (Activity: {gp.activity_score}%) is missing from your resume."
                project_suggestions.append({
                    "repo_name": gp.repo_name,
                    "technologies": gp.technologies,
                    "reason": reason,
                    "type": "project_addition"
                })

    # Map missing Certificate skills to specific certificate names
    cert_rows_result = await db.execute(
        select(Certificate)
        .where(Certificate.user_id == user_id)
    )
    user_certs = cert_rows_result.scalars().all()
    
    cert_gap_details = []
    for skill in sorted(cert_only):
        matching_certs = []
        for c in user_certs:
            if c.skills and any(s.lower() == skill.lower() for s in c.skills):
                matching_certs.append(c.name)
        if matching_certs:
            certs_str = ", ".join(matching_certs[:2])
            reason = f"Evidenced in your certificate '{certs_str}' but missing from your resume."
            cert_gap_details.append({
                "skill": skill,
                "reason": reason,
                "certs": matching_certs
            })
        else:
            cert_gap_details.append({
                "skill": skill,
                "reason": f"Evidenced in your certificates but missing from your resume.",
                "certs": []
            })

    # Map LeetCode gaps
    leetcode_gap_details = []
    for skill in sorted(leetcode_only):
        reason = f"Evidenced from your LeetCode problem solutions but missing from your resume."
        leetcode_gap_details.append({
            "skill": skill,
            "reason": reason
        })

    return {
        "github_gaps": github_gap_details,
        "leetcode_gaps": leetcode_gap_details,
        "certificate_gaps": cert_gap_details,
        "project_suggestions": project_suggestions
    }
