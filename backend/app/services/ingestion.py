from io import BytesIO
from datetime import datetime, timezone
from uuid import UUID
import re

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import User, Experience, Project
from app.models.structure import Skill, ProjectSkill
from app.models.inference import SkillEvidence, ProfileSnapshot

from app.services.pdf_parser import extract_text_from_pdf
from app.services.extraction import extract_resume_data
from app.services.skill_classifier import resolve_skills
from app.services.confidence import WEIGHTS, compute_skill_confidence
from app.services.review import flag_for_review


def _mentions_skill(text: str, raw_name: str) -> bool:
    """True if raw_name appears as a whole token in text, not as a
    substring inside another word (e.g. skill 'c' should not match
    inside 'architecture').
    """
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(raw_name.lower()) + r"(?![a-zA-Z0-9])"
    return re.search(pattern, text.lower()) is not None


async def _get_or_create_default_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(name="default", target_roles=[], target_companies=[])
        db.add(user)
        await db.flush()
    return user


async def _get_or_create_skill(db: AsyncSession, canonical_name: str, display_name: str) -> Skill:
    stmt = (
        pg_insert(Skill)
        .values(name=display_name, canonical_name=canonical_name)
        .on_conflict_do_nothing(index_elements=["canonical_name"])
        .returning(Skill.id)
    )
    result = await db.execute(stmt)
    skill_id = result.scalar_one_or_none()

    if skill_id is None:
        existing = await db.execute(
            select(Skill).where(Skill.canonical_name == canonical_name)
        )
        return existing.scalar_one()

    return Skill(id=skill_id, name=display_name, canonical_name=canonical_name)


async def ingest_resume(raw_bytes: bytes, db: AsyncSession) -> dict:
    # 1. Fetch: PDF -> raw text
    print(f"[TRACING] Starting PDF text extraction...", flush=True)
    raw_text = extract_text_from_pdf(BytesIO(raw_bytes))
    print(f"[TRACING] PDF text extraction complete. Extracted {len(raw_text)} characters.", flush=True)
    if not raw_text.strip():
        raise ValueError("No extractable text found in PDF")

    # 2. Extract: LLM call -> validated structured data
    print(f"[TRACING] Sending extracted text to LLM...", flush=True)
    extraction = await extract_resume_data(raw_text)
    print(f"[TRACING] LLM extraction complete.", flush=True)

    user = await _get_or_create_default_user(db)

    # 3. Store facts: experiences and projects, verbatim, append-only
    experience_rows: list[Experience] = []
    for exp in extraction.experiences:
        row = Experience(
            user_id=user.id,
            role=exp.role,
            company=exp.company,
            start_date=None,
            end_date=None,
            stack=exp.stack,
            bullets=exp.bullets,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        experience_rows.append(row)

    project_rows: list[Project] = []
    for proj in extraction.projects:
        row = Project(
            user_id=user.id,
            name=proj.name,
            description=proj.description,
            stack=proj.stack,
            repo_url=None,
            impact_metrics=None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        project_rows.append(row)

    await db.flush()

    # 4. Gather every raw skill string mentioned anywhere
    raw_skill_strings: set[str] = set(extraction.skills)
    for proj in extraction.projects:
        raw_skill_strings.update(proj.stack)
    for exp in extraction.experiences:
        raw_skill_strings.update(exp.stack)

    # 5. Hybrid resolution: dict -> DB cache -> batched LLM classification.
    #    Result maps each raw string to its canonical name, or None if it
    #    isn't a real skill at all (e.g. "Modular components").
    resolved = await resolve_skills(raw_skill_strings, db)

    canonical_to_raw: dict[str, str] = {}
    for raw, canonical in resolved.items():
        if canonical is not None:
            canonical_to_raw[canonical] = raw

    # 6. Structure: get-or-create each Skill row, link ProjectSkill
    skill_objs: dict[str, Skill] = {}
    for canonical, raw in canonical_to_raw.items():
        skill_objs[canonical] = await _get_or_create_skill(db, canonical, raw)

    for proj_row, proj_extracted in zip(project_rows, extraction.projects):
        for raw in proj_extracted.stack:
            canonical = resolved.get(raw)
            if canonical is None:
                continue
            skill = skill_objs[canonical]
            link_stmt = (
                pg_insert(ProjectSkill)
                .values(project_id=proj_row.id, skill_id=skill.id)
                .on_conflict_do_nothing()
            )
            await db.execute(link_stmt)

    # 7. Score confidence per canonical skill
    skills_json: dict[str, dict] = {}
    flagged: list[dict] = []

    for canonical, skill in skill_objs.items():
        evidence_entries: list[dict] = []
        weights: list[float] = []
        raw_name = canonical_to_raw[canonical].lower()

        for proj_row, proj_extracted in zip(project_rows, extraction.projects):
            stack_match = any(
                resolved.get(s) == canonical for s in proj_extracted.stack
            )
            desc_match = bool(proj_extracted.description) and _mentions_skill(
                proj_extracted.description, raw_name
            )
            if stack_match or desc_match:
                weights.append(WEIGHTS["project"])
                evidence_entries.append({
                    "source_type": "project",
                    "source_id": str(proj_row.id),
                    "detail": proj_extracted.name,
                })

        for exp_row, exp_extracted in zip(experience_rows, extraction.experiences):
            for bullet in exp_extracted.bullets:
                if _mentions_skill(bullet, raw_name):
                    weights.append(WEIGHTS["experience"])
                    evidence_entries.append({
                        "source_type": "experience",
                        "source_id": str(exp_row.id),
                        "detail": bullet,
                    })

        confidence = compute_skill_confidence(weights)

        for entry in evidence_entries:
            db.add(SkillEvidence(
                skill_id=skill.id,
                source_type=entry["source_type"],
                source_id=UUID(entry["source_id"]),
                weight=WEIGHTS[entry["source_type"]],
            ))

        skills_json[canonical] = {
            "confidence": confidence,
            "evidence": evidence_entries,
        }

        review_flag = flag_for_review(canonical, confidence)
        if review_flag:
            flagged.append(review_flag)

    # 8. Memory: write the profile snapshot
    snapshot = ProfileSnapshot(
        user_id=user.id,
        taken_at=datetime.now(timezone.utc),
        skills_json=skills_json,
        note="resume upload",
    )
    db.add(snapshot)
    await db.flush()

    await db.commit()

    return {
        "user_id": str(user.id),
        "experiences_created": len(experience_rows),
        "projects_created": len(project_rows),
        "skills_processed": len(skill_objs),
        "flagged_for_review": flagged,
        "snapshot_id": str(snapshot.id),
    }