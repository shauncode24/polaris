"""Chooses what goes on the resume tailored to one job, from the user's whole
evidence record (resume uploads, LinkedIn, GitHub, LeetCode).

Deterministic, no model calls. It only picks and orders: every line is the
evidence's own wording, so the result is already a usable resume, and the one
to fall back on when rewriting isn't possible.

Only current, visible evidence is used. Nothing the job asks for is listed
unless the user has evidence of it.
"""
import re
from datetime import date
from typing import get_args

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Education, Experience, Project, Resume, User
from app.models.github_analysis import GithubProjectAnalysis
from app.models.structure import Skill
from app.schemas.resume.tailored import (
    EducationEntry,
    ExperienceEntry,
    Header,
    Link,
    ProjectEntry,
    RankedEvidence,
    ResumeLine,
    Selection,
    SkillEntry,
    SourceKind,
    SourceRef,
    TailoredResumeDocument,
)
from app.services.evidence.confidence import (
    get_active_skill_evidence,
    get_hidden_skill_names,
    get_reconciled_skill_confidences,
)
from app.services.evidence.matching import known_canonicals, mentions_any, skill_aliases
from app.services.evidence.review import dedupe_visible
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.resume.claim_risk import apply_claim_risk_penalty, claim_risk_by_project_id
from app.services.resume.dates import is_ongoing
from app.services.resume.tailoring_ranking import TYPE_WEIGHTS, rank_items_for_jd

MAX_EXPERIENCES = 4
MAX_PROJECTS = 4
# Projects that match nothing are added only to reach this many.
MIN_PROJECTS = 2
MAX_EXPERIENCE_BULLETS = 5
MAX_PROJECT_BULLETS = 3
MAX_EDUCATION_LINES = 4
MAX_TECHNOLOGIES = 8
MAX_SKILLS = 18
MAX_SOURCES_PER_SKILL = 5

_BULLET_MARK = re.compile(r"^\s*(?:[-*•·‣▪]|\d+[.)])\s+")
_REQUIREMENT_ORDER = {"required": 0, "implicit": 1, "nice_to_have": 2}


def _newest_first(db_rows: list) -> list:
    return sorted(db_rows, key=lambda row: row.created_at, reverse=True)


def _resume_order(rows: list, uploaded_at: dict) -> list:
    """The latest upload's items first, each upload's in the order the resume
    listed them; then items from elsewhere. Dated items go newest first.
    """
    def listed(row):
        upload = uploaded_at.get(row.resume_id)
        return (0, -upload.timestamp(), row.created_at) if upload else (1, 0.0, row.created_at)

    def ended(row) -> date:
        if row.end_date:
            return row.end_date
        return date.max if row.start_date or is_ongoing(row.end_date_text) else date.min

    return sorted(sorted(rows, key=listed), key=ended, reverse=True)  # both sorts are stable


def _lines(
    texts: list[str], kind: str, row_id, limit: int, wanted: dict[str, str], aliases: dict[str, set[str]],
) -> list[ResumeLine]:
    """Up to `limit` lines, those showing most of what the job asks for first."""
    def relevance(text: str) -> float:
        return sum(TYPE_WEIGHTS[wanted[skill]] for skill, names in aliases.items() if mentions_any(text, names))

    numbered = [(number, text.strip()) for number, text in enumerate(texts) if text and text.strip()]
    best = sorted(numbered, key=lambda item: relevance(item[1]), reverse=True)[:limit]
    return [
        ResumeLine(original=text, sources=[SourceRef(kind=kind, id=row_id, bullet=number)])
        for number, text in best
    ]


def _description_lines(description: str | None) -> list[str]:
    """A project description holds one bullet per line."""
    return [_BULLET_MARK.sub("", line) for line in (description or "").splitlines()]


def _technologies(
    names: list[str], canonical_of: dict[str, str], wanted: dict[str, str], hidden: set[str],
) -> list[str]:
    """The names without repeats or hidden skills, what the job asks for first."""
    unique: dict[str, tuple[str, str | None]] = {}
    for name in names:
        canonical = canonical_of.get(name)
        if canonical in hidden or name.strip().lower() in hidden:
            continue
        unique.setdefault(canonical or name.strip().lower(), (name.strip(), canonical))
    ordered = sorted(unique.values(), key=lambda item: _REQUIREMENT_ORDER.get(wanted.get(item[1]), 3))
    return [name for name, _canonical in ordered[:MAX_TECHNOLOGIES]]


def _header(user: User) -> Header:
    full_name = " ".join(filter(None, [user.first_name, user.last_name])) or user.name
    links = []
    if user.github_username:
        links.append(Link(label="GitHub", url=f"https://github.com/{user.github_username}"))
    return Header(full_name=full_name or "Your name", email=user.email, links=links)


async def _rows(db: AsyncSession, model, user_id) -> list:
    return list((await db.execute(select(model).where(model.user_id == user_id))).scalars().all())


async def select_for_job(db: AsyncSession, user_id, job_intelligence_id) -> Selection | None:
    """The resume content chosen for this job, and how each experience and
    project ranked. None when the user has no such job.
    """
    job = await get_job_intelligence(db, user_id, job_intelligence_id)
    if job is None:
        return None

    hidden = await get_hidden_skill_names(db, user_id)
    wanted = {skill: kind for skill, kind in job.canonical_skills_map.items() if skill not in hidden}
    evidence = await get_active_skill_evidence(db, user_id)
    skills_of: dict[tuple, set[str]] = {}
    for canonical, rows in evidence.items():
        for row in rows:
            skills_of.setdefault((row.source_type, row.source_id), set()).add(canonical)

    uploaded_at = dict((await db.execute(
        select(Resume.id, Resume.created_at).where(Resume.user_id == user_id)
    )).all())
    experiences = _resume_order(
        dedupe_visible("experiences", _newest_first(await _rows(db, Experience, user_id))), uploaded_at,
    )
    projects = dedupe_visible("projects", _newest_first(await _rows(db, Project, user_id)))
    education = _resume_order(
        dedupe_visible("education", _newest_first(await _rows(db, Education, user_id))), uploaded_at,
    )
    repos = {a.repo_name: a for a in await _rows(db, GithubProjectAnalysis, user_id)}

    def repo_of(project: Project):
        return repos.get(project.github_repo_name) if project.github_repo_name else None

    def stack_of(row) -> list[str]:
        repo = repo_of(row) if isinstance(row, Project) else None
        return [s for s in [*(row.stack or []), *((repo.technologies or []) if repo else [])] if s and s.strip()]

    canonical_of = await known_canonicals(db, {s for row in [*experiences, *projects] for s in stack_of(row)})

    def item(row, kind: str, label: str) -> dict:
        found = set(skills_of.get((kind, row.id), ()))
        repo = repo_of(row) if kind == "project" else None
        if repo is not None:
            found |= skills_of.get(("github_repo", repo.id), set())
        found |= {canonical_of[s] for s in stack_of(row) if s in canonical_of}
        return {"id": str(row.id), "type": kind, "label": label, "canonical_stack": sorted(found)}

    ranked = rank_items_for_jd(
        [item(e, "experience", f"{e.role} at {e.company}") for e in experiences]
        + [item(p, "project", p.name) for p in projects],
        wanted,
    )
    risks = await claim_risk_by_project_id(db, [p.id for p in projects])
    risks = {str(project_id): level for project_id, level in risks.items()}
    for entry in ranked:
        entry["claim_risk"] = risks.get(entry["id"])
        entry["relevance_score"] = round(apply_claim_risk_penalty(entry["relevance_score"], entry["claim_risk"]), 2)
    ranked.sort(key=lambda entry: entry["relevance_score"], reverse=True)  # ties keep their order

    # Experiences: the most relevant, shown in resume order.
    roles = [e for e in experiences if e.role.strip() and e.company.strip()]
    role_ids = {str(e.id) for e in roles}
    chosen_roles = set([r["id"] for r in ranked if r["id"] in role_ids][:MAX_EXPERIENCES])
    chosen_experiences = [e for e in roles if str(e.id) in chosen_roles]

    # Projects: the relevant ones, most relevant first.
    projects_by_id = {str(p.id): p for p in projects if p.name.strip()}
    ranked_projects = [r for r in ranked if r["id"] in projects_by_id]
    chosen = [r for r in ranked_projects if r["relevance_score"] > 0][:MAX_PROJECTS]
    if len(chosen) < MIN_PROJECTS:
        others = [r for r in ranked_projects if r not in chosen]
        others.sort(key=lambda r: not (projects_by_id[r["id"]].description or "").strip())  # described first
        chosen += others[:MIN_PROJECTS - len(chosen)]
    chosen_projects = [projects_by_id[r["id"]] for r in chosen]

    aliases = await skill_aliases(db, set(wanted))

    def experience_entry(e: Experience) -> ExperienceEntry:
        return ExperienceEntry(
            role=e.role.strip(), company=e.company.strip(), start_date=e.start_date, end_date=e.end_date,
            start_date_text=e.start_date_text, end_date_text=e.end_date_text,
            bullets=_lines(e.bullets or [], "experience", e.id, MAX_EXPERIENCE_BULLETS, wanted, aliases),
            sources=[SourceRef(kind="experience", id=e.id)],
        )

    def project_entry(p: Project) -> ProjectEntry:
        repo = repo_of(p)
        sources = [SourceRef(kind="project", id=p.id)]
        if repo is not None:
            sources.append(SourceRef(kind="github_repo", id=repo.id))
        return ProjectEntry(
            name=p.name.strip(), url=p.repo_url or (repo.html_url if repo else None),
            technologies=_technologies(stack_of(p), canonical_of, wanted, hidden),
            bullets=_lines(_description_lines(p.description), "project", p.id, MAX_PROJECT_BULLETS, wanted, aliases),
            sources=sources,
        )

    def education_entry(e: Education) -> EducationEntry:
        return EducationEntry(
            institution=e.institution.strip(), degree=e.degree, field_of_study=e.field_of_study,
            start_date=e.start_date, end_date=e.end_date, is_current=bool(e.is_current),
            start_date_text=e.start_date_text, end_date_text=e.end_date_text,
            bullets=_lines(e.details or [], "education", e.id, MAX_EDUCATION_LINES, wanted, aliases),
            sources=[SourceRef(kind="education", id=e.id)],
        )

    document = TailoredResumeDocument(
        header=_header(await db.get(User, user_id)),
        experience=[experience_entry(e) for e in chosen_experiences],
        projects=[project_entry(p) for p in chosen_projects],
        education=[education_entry(e) for e in education if e.institution.strip()],
        skills=await _skills(
            db, user_id, evidence, wanted, [*chosen_experiences, *chosen_projects], stack_of, canonical_of,
        ),
    )
    selected = chosen_roles | {r["id"] for r in chosen}
    return Selection(
        document=document,
        ranking=[RankedEvidence(**entry, selected=entry["id"] in selected) for entry in ranked],
    )


async def _skills(db, user_id, evidence, wanted, chosen_rows, stack_of, canonical_of) -> list[SkillEntry]:
    """The skills to list: what the job asks for first, then the best
    evidenced. LeetCode practice alone lists a skill only if the job asks.
    """
    # Only evidence that can be pointed at (older data may hold other kinds).
    usable = {
        canonical: [
            row for row in rows
            if row.source_type in get_args(SourceKind)
            and (row.source_id is not None or row.source_type == "leetcode_tag")
        ]
        for canonical, rows in evidence.items()
    }
    listed = {
        canonical: rows for canonical, rows in usable.items()
        if rows and (canonical in wanted or any(row.source_type != "leetcode_tag" for row in rows))
    }
    if not listed:
        return []
    confidence = await get_reconciled_skill_confidences(db, user_id)

    def order(canonical: str):
        return (
            _REQUIREMENT_ORDER.get(wanted.get(canonical), 3),
            -confidence.get(canonical, {}).get("confidence", 0.0),
            canonical,
        )

    chosen = sorted(listed, key=order)[:MAX_SKILLS]

    # Named as the user writes it where possible.
    written: dict[str, str] = {}
    for row in chosen_rows:
        for name in stack_of(row):
            if name in canonical_of:
                written.setdefault(canonical_of[name], name.strip())
    stored = dict((await db.execute(
        select(Skill.canonical_name, Skill.name).where(Skill.canonical_name.in_(chosen))
    )).all())

    entries = []
    for canonical in chosen:
        sources: dict[tuple, SourceRef] = {}
        for row in listed[canonical]:  # strongest first
            row_id = None if row.source_type == "leetcode_tag" else row.source_id
            sources.setdefault((row.source_type, row_id), SourceRef(kind=row.source_type, id=row_id))
        entries.append(SkillEntry(
            name=written.get(canonical) or stored.get(canonical) or canonical.replace("_", " "),
            canonical=canonical, sources=list(sources.values())[:MAX_SOURCES_PER_SKILL],
        ))
    return entries
