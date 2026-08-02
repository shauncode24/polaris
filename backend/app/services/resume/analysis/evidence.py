"""Module 7 — Evidence Checker.

For each skill associated with the user's resume, checks whether there
is corroborating evidence in: Projects, Experience, or GitHub.

Assigns a CORROBORATION level (high / medium / low) per skill based on
how many independent SOURCES back it up. This is deliberately NOT called
"confidence" — the canonical, numeric confidence score lives in
resume/confidence.py's decayed-weight formula.
"""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Experience, Project, GithubSnapshot, Certificate
from app.models.structure import Skill, ProjectSkill
from app.models.inference import SkillEvidence, ProfileSnapshot
from app.models.github_analysis import GithubProjectAnalysis


async def analyze_evidence(
    db: AsyncSession,
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
) -> dict:
    exp_rows = await db.execute(
        select(Experience.id).where(
            Experience.user_id == user_id,
            Experience.resume_id == resume_id,
        )
    )
    exp_ids: set[str] = {str(r[0]) for r in exp_rows.fetchall()}

    proj_rows = await db.execute(
        select(Project.id).where(
            Project.user_id == user_id,
            Project.resume_id == resume_id,
        )
    )
    proj_ids: set[str] = {str(r[0]) for r in proj_rows.fetchall()}

    all_source_ids = list(exp_ids | proj_ids)

    if not all_source_ids:
        return {
            "score": 0,
            "skills": [],
            "total_skills": 0,
            "high_corroboration": 0,
            "medium_corroboration": 0,
            "low_corroboration": 0,
        }

    # FIX (cross-user evidence leak): all three queries below now also
    # filter on SkillEvidence.user_id. The project/experience query was
    # already effectively safe (source_id is a real UUID PK, so it can't
    # collide across users), but the leetcode/certificate queries join
    # on tag/skill NAME rather than a user-scoped foreign key, so without
    # this filter they could match a SkillEvidence row belonging to a
    # different user who happens to have evidence for the same skill.
    ev_rows = await db.execute(
        select(SkillEvidence.skill_id, SkillEvidence.source_id, SkillEvidence.source_type)
        .where(
            SkillEvidence.source_id.in_([uuid.UUID(sid) for sid in all_source_ids]),
            SkillEvidence.user_id == user_id,
        )
    )
    evidence_list = list(ev_rows.fetchall())



    cert_ev_rows = await db.execute(
        select(SkillEvidence.skill_id, SkillEvidence.source_id, SkillEvidence.source_type)
        .join(Certificate, SkillEvidence.source_id == Certificate.id)
        .where(
            Certificate.user_id == user_id,
            SkillEvidence.source_type == "certificate",
            SkillEvidence.user_id == user_id,
        )
    )
    evidence_list.extend(cert_ev_rows.fetchall())

    skill_ids = {row[0] for row in evidence_list}
    skill_rows = await db.execute(
        select(Skill.id, Skill.name, Skill.canonical_name).where(Skill.id.in_(skill_ids))
    ) if skill_ids else None

    skill_map: dict[str, dict] = {}
    if skill_rows:
        for sid, name, canonical in skill_rows.fetchall():
            skill_map[str(sid)] = {"name": name, "canonical": canonical}

    proj_skill_rows = await db.execute(
        select(ProjectSkill.project_id, ProjectSkill.skill_id, Skill.name, Skill.canonical_name)
        .join(Skill, ProjectSkill.skill_id == Skill.id)
        .where(ProjectSkill.project_id.in_([uuid.UUID(pid) for pid in proj_ids]))
    ) if proj_ids else None

    project_skill_set: dict[str, dict] = {}
    if proj_skill_rows:
        for proj_id, skill_id, name, canonical in proj_skill_rows.fetchall():
            if canonical not in project_skill_set:
                project_skill_set[canonical] = {
                    "name": name,
                    "canonical": canonical,
                    "in_experience": False,
                    "in_project": True,
                    "in_certificate": False,
                    "skill_id": str(skill_id),
                }
            else:
                project_skill_set[canonical]["in_project"] = True

    snapshot_result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id, ProfileSnapshot.note == "resume upload")
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    snapshot = snapshot_result.scalar_one_or_none()

    resume_skills_set = set()
    if snapshot and snapshot.skills_json:
        resume_skills_set = {k.lower() for k in snapshot.skills_json.keys()}

    linked_resume_skills_set = set()
    for canonical in project_skill_set.keys():
        linked_resume_skills_set.add(canonical.lower())
    for skill_id, source_id, source_type in evidence_list:
        if source_type in ("experience", "project"):
            sid = str(skill_id)
            info = skill_map.get(sid, {})
            canonical = info.get("canonical", sid)
            linked_resume_skills_set.add(canonical.lower())

    all_resume_skills = resume_skills_set | linked_resume_skills_set

    skill_evidence: dict[str, dict] = {}

    if all_resume_skills:
        all_skills_query = await db.execute(
            select(Skill.id, Skill.name, Skill.canonical_name)
            .where(Skill.canonical_name.in_(list(all_resume_skills)))
        )
        for skill_id, name, canonical in all_skills_query.fetchall():
            canonical_lower = canonical.lower()
            skill_evidence[canonical_lower] = {
                "name": name,
                "canonical": canonical,
                "in_experience": False,
                "in_project": False,
                "in_certificate": False,
                "skill_id": str(skill_id),
            }

        for canonical, info in project_skill_set.items():
            canonical_lower = canonical.lower()
            if canonical_lower in skill_evidence:
                skill_evidence[canonical_lower]["in_project"] = True

        for skill_id, source_id, source_type in evidence_list:
            sid = str(skill_id)
            info = skill_map.get(sid, {})
            canonical = info.get("canonical", sid)
            canonical_lower = canonical.lower()

            if canonical_lower in skill_evidence:
                if source_type == "experience":
                    skill_evidence[canonical_lower]["in_experience"] = True
                elif source_type == "project":
                    skill_evidence[canonical_lower]["in_project"] = True
                elif source_type == "certificate":
                    skill_evidence[canonical_lower]["in_certificate"] = True
    else:
        skill_evidence = dict(project_skill_set)
        for skill_id, source_id, source_type in evidence_list:
            sid = str(skill_id)
            info = skill_map.get(sid, {})
            canonical = info.get("canonical", sid)
            if canonical not in skill_evidence:
                skill_evidence[canonical] = {
                    "name": info.get("name", canonical),
                    "canonical": canonical,
                    "in_experience": False,
                    "in_project": False,
                    "in_certificate": False,
                    "skill_id": sid,
                }
            if source_type == "experience":
                skill_evidence[canonical]["in_experience"] = True
            elif source_type == "project":
                skill_evidence[canonical]["in_project"] = True
            elif source_type == "certificate":
                skill_evidence[canonical]["in_certificate"] = True

    gh_rows = await db.execute(
        select(GithubSnapshot.languages).where(GithubSnapshot.user_id == user_id)
    )
    github_langs: set[str] = set()
    for row in gh_rows.fetchall():
        langs = row[0]
        if langs:
            github_langs.update(k.lower() for k in langs.keys())

    gh_tech_rows = await db.execute(
        select(GithubProjectAnalysis.technologies).where(GithubProjectAnalysis.user_id == user_id)
    )
    for row in gh_tech_rows.fetchall():
        techs = row[0]
        if techs:
            github_langs.update(t.lower() for t in techs)

    skills_list: list[dict] = []
    high_corr = medium_corr = low_corr = 0

    for canonical, data in skill_evidence.items():
        in_gh = canonical.lower() in github_langs or data.get("name", "").lower() in github_langs
        data["in_github"] = in_gh

        in_certificate = data.get("in_certificate", False)

        source_count = sum([
            data["in_experience"],
            data["in_project"],
            in_gh,
            in_certificate,
        ])
        data["corroboration_count"] = source_count

        if source_count >= 3:
            data["corroboration_level"] = "high"
            high_corr += 1
        elif source_count >= 1:
            data["corroboration_level"] = "medium"
            medium_corr += 1
        else:
            data["corroboration_level"] = "low"
            low_corr += 1

        data["confidence"] = data["corroboration_level"]
        skills_list.append({k: v for k, v in data.items() if k != "skill_id"})

    total = len(skills_list)
    if total > 0:
        score = round(((high_corr * 1.0 + medium_corr * 0.6 + low_corr * 0.15) / total) * 100)
    else:
        score = 0

    order = {"high": 0, "medium": 1, "low": 2}
    skills_list.sort(key=lambda s: (order.get(s["corroboration_level"], 3), s.get("name", "")))

    return {
        "score": min(100, score),
        "skills": skills_list,
        "total_skills": total,
        "high_corroboration": high_corr,
        "medium_corroboration": medium_corr,
        "low_corroboration": low_corr,
    }