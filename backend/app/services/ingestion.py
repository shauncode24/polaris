from io import BytesIO
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import User, Experience, Project
from app.models.structure import Skill, ProjectSkill
from app.models.inference import SkillEvidence, ProfileSnapshot

from app.services.pdf_parser import extract_text_from_pdf
from app.services.extraction import extract_resume_data
from app.services.skill_normalizer import normalize_skill
from app.services.confidence import WEIGHTS, compute_skill_confidence
from app.services.review import flag_for_review


async def _get_or_create_default_user(db: AsyncSession) -> User:
    """Single-user MVP: reuse the first user row, or create one.

    Every table is already scoped by user_id (per Open Decision #1 in
    the design doc), so multi-user support later is a routing change,
    not a schema change.
    """
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(name="default", target_roles=[], target_companies=[])
        db.add(user)
        await db.flush()  # assigns user.id without committing
    return user


async def _get_or_create_skill(db: AsyncSession, canonical_name: str, display_name: str) -> Skill:
    """Insert the skill if new, otherwise fetch the existing row.

    Skills are shared across all data (not per-user), so this is a
    global upsert keyed on canonical_name's unique index.
    """
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
    """Full Phase 2 pipeline: PDF -> LLM extraction -> normalize ->
    confidence scoring -> facts + inference rows + a profile snapshot.

    Everything below runs in a single transaction. If anything fails
    partway (bad LLM output, a DB constraint violation), the whole
    ingestion rolls back rather than leaving half a resume committed
    with no matching evidence.
    """
    # 1. Fetch: PDF -> raw text
    raw_text = extract_text_from_pdf(BytesIO(raw_bytes))
    if not raw_text.strip():
        raise ValueError("No extractable text found in PDF")

    # 2. Extract: LLM call -> validated structured data
    extraction = await extract_resume_data(raw_text)

    user = await _get_or_create_default_user(db)

    # 3. Store facts: experiences and projects, verbatim from the LLM,
    #    append-only, never overwritten (§5.5 facts vs inference).
    experience_rows: list[Experience] = []
    for exp in extraction.experiences:
        row = Experience(
            user_id=user.id,
            role=exp.role,
            company=exp.company,
            start_date=None,  # left as None until we add real date parsing
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

    await db.flush()  # assigns ids to experience_rows / project_rows

    # 4. Normalize: build the full set of raw skill strings mentioned
    #    anywhere (explicit skills list + every project/experience stack),
    #    and map each to its canonical name.
    raw_skill_strings: set[str] = set(extraction.skills)
    for proj in extraction.projects:
        raw_skill_strings.update(proj.stack)
    for exp in extraction.experiences:
        raw_skill_strings.update(exp.stack)

    canonical_to_raw: dict[str, str] = {}
    for raw in raw_skill_strings:
        canonical_to_raw[normalize_skill(raw)] = raw

    # 5. Structure: get-or-create each Skill row, link ProjectSkill
    skill_objs: dict[str, Skill] = {}
    for canonical, raw in canonical_to_raw.items():
        skill_objs[canonical] = await _get_or_create_skill(db, canonical, raw)

    for proj_row, proj_extracted in zip(project_rows, extraction.projects):
        for raw in proj_extracted.stack:
            canonical = normalize_skill(raw)
            skill = skill_objs[canonical]
            link_stmt = (
                pg_insert(ProjectSkill)
                .values(project_id=proj_row.id, skill_id=skill.id)
                .on_conflict_do_nothing()
            )
            await db.execute(link_stmt)

    # 6. Score confidence: gather (source_type, source_id, weight) per
    #    canonical skill, write one SkillEvidence row per source.
    skills_json: dict[str, dict] = {}
    flagged: list[dict] = []

    for canonical, skill in skill_objs.items():
        evidence_entries: list[dict] = []
        weights: list[float] = []

        # Project evidence: this skill appears in a project's stack
        for proj_row, proj_extracted in zip(project_rows, extraction.projects):
            if any(normalize_skill(s) == canonical for s in proj_extracted.stack):
                weights.append(WEIGHTS["project"])
                evidence_entries.append({
                    "source_type": "project",
                    "source_id": str(proj_row.id),
                    "detail": proj_extracted.name,
                })

        # Experience evidence: this skill is mentioned in a bullet.
        # Counted per bullet, per the +0.25/bullet rule in §4.3 —
        # NOT per experience.stack entry, to avoid double-counting
        # the same evidence twice.
        raw_name = canonical_to_raw[canonical].lower()
        for exp_row, exp_extracted in zip(experience_rows, extraction.experiences):
            for bullet in exp_extracted.bullets:
                if raw_name in bullet.lower():
                    weights.append(WEIGHTS["experience"])
                    evidence_entries.append({
                        "source_type": "experience",
                        "source_id": str(exp_row.id),
                        "detail": bullet,
                    })

        # Certificates and LeetCode tags aren't ingested until later
        # phases (Phase 3+), so their weights simply contribute nothing
        # yet — the formula is already correct, the data just isn't
        # there.

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

    # 7. Memory: write the first profile_snapshots row for this ingestion
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