"""Module 7 — Evidence Checker.

For each skill associated with the user's resume, checks whether there
is corroborating evidence in: Projects, Experience, or GitHub.

Assigns a confidence level (high / medium / low) per skill based on
how many sources back it up.
"""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Experience, Project, GithubSnapshot, LeetcodeSnapshot, Certificate
from app.models.structure import Skill, ProjectSkill
from app.models.inference import SkillEvidence, ProfileSnapshot


async def analyze_evidence(
    db: AsyncSession,
    user_id: uuid.UUID,
    resume_id: uuid.UUID,
) -> dict:
    # ── Fetch experience & project IDs for this resume ─────────────────────
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
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
        }

    # ── Fetch skill evidence linked to those sources ────────────────────────
    # 1. Experience & Project evidence for this resume
    ev_rows = await db.execute(
        select(SkillEvidence.skill_id, SkillEvidence.source_id, SkillEvidence.source_type)
        .where(SkillEvidence.source_id.in_([uuid.UUID(sid) for sid in all_source_ids]))
    )
    evidence_list = list(ev_rows.fetchall())

    # 2. Leetcode evidence for this user
    lc_ev_rows = await db.execute(
        select(SkillEvidence.skill_id, SkillEvidence.source_id, SkillEvidence.source_type)
        .join(Skill, SkillEvidence.skill_id == Skill.id)
        .join(
            LeetcodeSnapshot,
            (LeetcodeSnapshot.tag == Skill.name) | (LeetcodeSnapshot.tag == Skill.canonical_name)
        )
        .where(LeetcodeSnapshot.user_id == user_id, SkillEvidence.source_type == "leetcode_tag")
    )
    evidence_list.extend(lc_ev_rows.fetchall())

    # 3. Certificate evidence for this user
    cert_ev_rows = await db.execute(
        select(SkillEvidence.skill_id, SkillEvidence.source_id, SkillEvidence.source_type)
        .join(Certificate, SkillEvidence.source_id == Certificate.id)
        .where(Certificate.user_id == user_id, SkillEvidence.source_type == "certificate")
    )
    evidence_list.extend(cert_ev_rows.fetchall())

    # ── Fetch skill display names ───────────────────────────────────────────
    skill_ids = {row[0] for row in evidence_list}
    skill_rows = await db.execute(
        select(Skill.id, Skill.name, Skill.canonical_name).where(Skill.id.in_(skill_ids))
    ) if skill_ids else None

    skill_map: dict[str, dict] = {}
    if skill_rows:
        for sid, name, canonical in skill_rows.fetchall():
            skill_map[str(sid)] = {"name": name, "canonical": canonical}

    # ── Also pull project skills via ProjectSkill join ──────────────────────
    proj_skill_rows = await db.execute(
        select(ProjectSkill.project_id, ProjectSkill.skill_id, Skill.name, Skill.canonical_name)
        .join(Skill, ProjectSkill.skill_id == Skill.id)
        .where(ProjectSkill.project_id.in_([uuid.UUID(pid) for pid in proj_ids]))
    ) if proj_ids else None

    project_skill_set: dict[str, dict] = {}  # canonical → info
    if proj_skill_rows:
        for proj_id, skill_id, name, canonical in proj_skill_rows.fetchall():
            if canonical not in project_skill_set:
                project_skill_set[canonical] = {
                    "name": name,
                    "canonical": canonical,
                    "in_experience": False,
                    "in_project": True,
                    "in_leetcode": False,
                    "in_certificate": False,
                    "skill_id": str(skill_id),
                }
            else:
                project_skill_set[canonical]["in_project"] = True

    # ── Fetch resume skills from latest snapshot to show all of them ────────
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

    # Merge ProjectSkill keys and Experience/Project linked SkillEvidence canonicals
    linked_resume_skills_set = set()
    for canonical in project_skill_set.keys():
        linked_resume_skills_set.add(canonical.lower())
    for skill_id, source_id, source_type in evidence_list:
        if source_type in ("experience", "project"):
            sid = str(skill_id)
            info = skill_map.get(sid, {})
            canonical = info.get("canonical", sid)
            linked_resume_skills_set.add(canonical.lower())

    # Complete set of resume skills
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
                "in_leetcode": False,
                "in_certificate": False,
                "skill_id": str(skill_id),
            }

        # Merge project_skill_set evidence
        for canonical, info in project_skill_set.items():
            canonical_lower = canonical.lower()
            if canonical_lower in skill_evidence:
                skill_evidence[canonical_lower]["in_project"] = True

        # Merge SkillEvidence rows
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
                elif source_type == "leetcode_tag":
                    skill_evidence[canonical_lower]["in_leetcode"] = True
                elif source_type == "certificate":
                    skill_evidence[canonical_lower]["in_certificate"] = True
    else:
        # Fallback old behavior
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
                    "in_leetcode": False,
                    "in_certificate": False,
                    "skill_id": sid,
                }
            if source_type == "experience":
                skill_evidence[canonical]["in_experience"] = True
            elif source_type == "project":
                skill_evidence[canonical]["in_project"] = True
            elif source_type == "leetcode_tag":
                skill_evidence[canonical]["in_leetcode"] = True
            elif source_type == "certificate":
                skill_evidence[canonical]["in_certificate"] = True

    # ── GitHub language evidence ────────────────────────────────────────────
    gh_rows = await db.execute(
        select(GithubSnapshot.languages).where(GithubSnapshot.user_id == user_id)
    )
    github_langs: set[str] = set()
    for row in gh_rows.fetchall():
        langs = row[0]
        if langs:
            github_langs.update(k.lower() for k in langs.keys())

    # ── Assign confidence ───────────────────────────────────────────────────
    skills_list: list[dict] = []
    high_conf = medium_conf = low_conf = 0

    for canonical, data in skill_evidence.items():
        in_gh = canonical.lower() in github_langs or data.get("name", "").lower() in github_langs
        data["in_github"] = in_gh

        in_leetcode = data.get("in_leetcode", False)
        in_certificate = data.get("in_certificate", False)

        sources = sum([
            data["in_experience"],
            data["in_project"],
            in_gh,
            in_leetcode,
            in_certificate
        ])

        if sources >= 3:
            data["confidence"] = "high"
            high_conf += 1
        elif sources >= 1:
            data["confidence"] = "medium"
            medium_conf += 1
        else:
            data["confidence"] = "low"
            low_conf += 1

        skills_list.append({k: v for k, v in data.items() if k != "skill_id"})

    total = len(skills_list)
    if total > 0:
        score = round(((high_conf * 1.0 + medium_conf * 0.6 + low_conf * 0.15) / total) * 100)
    else:
        score = 0

    # Sort: high → medium → low, then alphabetically
    order = {"high": 0, "medium": 1, "low": 2}
    skills_list.sort(key=lambda s: (order.get(s["confidence"], 3), s.get("name", "")))

    return {
        "score": min(100, score),
        "skills": skills_list,
        "total_skills": total,
        "high_confidence": high_conf,
        "medium_confidence": medium_conf,
        "low_confidence": low_conf,
    }
