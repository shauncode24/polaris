# backend/app/services/interview/context_builder.py
"""Gathers the candidate's real profile, ranks and caps it against the
ACTUAL question being asked, and hands the shortlist to the LLM — not
the entire profile, undifferentiated, every time.

Interview Agent implementation plan §C/§D (Phase 0): retrieval is now a
deterministic ranking pass, not a raw dump. Each project/experience is
scored on:
  - competency match (does it evidence a competency this blueprint
    actually cares about? — see blueprints.BLUEPRINT_COMPETENCY_HINTS)
  - JD overlap (does its stack overlap the target role's required
    technologies, when a target job is given?)
  - evidence confidence (how strongly is its stack corroborated
    elsewhere in the candidate's profile?)
  - recency (rows already arrive most-recent-first from the DB query,
    so position is a free, honest recency proxy)
then capped to the top MAX_PROJECTS_IN_CONTEXT / MAX_EXPERIENCES_IN_CONTEXT.
Capping never drops a category to zero and never hides evidence that
scores well — it only stops sending a long tail of low-relevance items
that previously diluted the prompt on every single call regardless of
what was actually asked.

Competency tags are read from Project.competency_tags /
Experience.competency_tags when present, and lazily backfilled (tier-1
deterministic, tier-2 LLM+cache) via competency_tagging.tag_or_backfill_items
on first read — see that module's docstring. The backfill write rides
along on whatever commit the caller (api/interview.py) performs after
this function returns; nothing here commits on its own.

Engineering Identity integration (implementation plan §3/§5): the
framing/self-knowledge layer (top_skills summary, role_fit,
engineering_quadrant, company_readiness, claim_risk_details,
coverage_gaps, evidence_coverage) is sourced from the single shared
identity_context adapter — see identity_context.py for the interview-
specific slimming applied there (dedup, dropped unused fields).
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import CompanyNote, Education, Experience, Project
from app.models.inference import InterviewResponse, ProfileSnapshot
from app.services.interview.blueprints import get_blueprint_competency_hints, get_blueprint_library, get_persona
from app.services.interview.competency_tagging import tag_or_backfill_items
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.identity.identity_context import build_identity_context_for_interview
from app.services.identity.reconciled_confidence import get_reconciled_skill_confidences
from app.services.resume.skill_classifier import resolve_skills

from app.services.projects.linking import normalize_name

from app.models.github_analysis import GithubProjectAnalysis

MAX_CONVERSATION_TURNS = 6

# Token-budget caps — see module docstring. Generous enough that a
# genuinely thin profile never feels artificially trimmed; tight enough
# that a large profile stops paying (in tokens and in signal dilution)
# for evidence the current question has no real use for.
MAX_SKILLS_IN_CONTEXT = 25
MAX_EDUCATION_IN_CONTEXT = 4
MAX_PROJECTS_IN_CONTEXT = 8
MAX_EXPERIENCES_IN_CONTEXT = 8


def _project_text(p: Project) -> str:
    return f"{p.description or ''} {' '.join(p.stack or [])}"


def _experience_text(e: Experience) -> str:
    return f"{' '.join(e.bullets or [])} {' '.join(e.stack or [])}"


async def _load_projects_with_tags(db: AsyncSession, user_id) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
    )
    all_p = result.scalars().all()
    seen: set[str] = set()
    projects: list[Project] = []
    for p in all_p:
        norm = normalize_name(p.name)
        if norm not in seen:
            seen.add(norm)
            projects.append(p)

    items = [
        {"key": str(p.id), "text": _project_text(p), "existing_tags": p.competency_tags}
        for p in projects
    ]
    tags_by_key = await tag_or_backfill_items(db, items)
    for p in projects:
        if p.competency_tags is None:
            p.competency_tags = tags_by_key.get(str(p.id), [])
    return projects


async def _load_experiences_with_tags(db: AsyncSession, user_id) -> list[Experience]:
    result = await db.execute(
        select(Experience)
        .where(Experience.user_id == user_id)
        .order_by(Experience.start_date.desc().nullsfirst(), Experience.created_at.desc())
    )
    all_e = result.scalars().all()
    seen: set[str] = set()
    experiences: list[Experience] = []
    for e in all_e:
        key = f"{normalize_name(e.role)}@{normalize_name(e.company)}"
        if key not in seen:
            seen.add(key)
            experiences.append(e)

    items = [
        {"key": str(e.id), "text": _experience_text(e), "existing_tags": e.competency_tags}
        for e in experiences
    ]
    tags_by_key = await tag_or_backfill_items(db, items)
    for e in experiences:
        if e.competency_tags is None:
            e.competency_tags = tags_by_key.get(str(e.id), [])
    return experiences


def _rank_and_cap(
    rows: list,
    *,
    stack_of,
    tags_of,
    to_dict,
    competency_hints: set[str],
    required_technologies: set[str],
    canonical_by_raw: dict[str, str | None],
    confidence_by_canonical: dict[str, float],
    max_items: int,
) -> list[dict]:
    """Deterministic ranking formula — every weight below is explainable
    in one sentence, same philosophy as github_scoring.score_repository().
    Rows already arrive most-recent-first from the caller's DB query.
    """
    total = len(rows)
    scored: list[tuple[float, object]] = []

    for idx, row in enumerate(rows):
        tags = set(tags_of(row) or [])
        tag_score = 1.0 if (competency_hints and tags & competency_hints) else 0.0

        canonicals = {canonical_by_raw.get(s) for s in (stack_of(row) or [])}
        canonicals.discard(None)
        jd_overlap = len(canonicals & required_technologies) if required_technologies else 0

        confidences = [confidence_by_canonical[c] for c in canonicals if c in confidence_by_canonical]
        confidence_score = sum(confidences) / len(confidences) if confidences else 0.0

        recency_score = max(0.0, 1.0 - (idx / max(total, 1)))

        score = (tag_score * 3.0) + (jd_overlap * 1.5) + (confidence_score * 1.0) + (recency_score * 0.5)
        scored.append((score, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [to_dict(row) for _, row in scored[:max_items]]


async def _get_confidence_map(db: AsyncSession, user_id) -> dict[str, float]:
    reconciled = await get_reconciled_skill_confidences(db, user_id)
    return {canonical: entry["confidence"] for canonical, entry in reconciled.items()}


def _slim_skills(confidence_by_canonical: dict[str, float]) -> list[dict]:
    ranked = sorted(confidence_by_canonical.items(), key=lambda kv: kv[1], reverse=True)
    return [{"skill": s, "confidence": c} for s, c in ranked[:MAX_SKILLS_IN_CONTEXT]]


async def _get_all_education(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(
        select(Education)
        .where(Education.user_id == user_id)
        .order_by(Education.end_date.desc().nullsfirst(), Education.created_at.desc())
    )
    all_edu = result.scalars().all()
    seen = set()
    education = []
    for e in all_edu:
        key = f"{normalize_name(e.institution)}@{normalize_name(e.degree or '')}"
        if key not in seen:
            seen.add(key)
            education.append({
                "type": "education",
                "institution": e.institution,
                "degree": e.degree,
                "field_of_study": e.field_of_study,
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "end_date": e.end_date.isoformat() if e.end_date else None,
                "is_current": e.is_current,
                "details": e.details or [],
            })
    return education[:MAX_EDUCATION_IN_CONTEXT]


async def _get_company_notes(db: AsyncSession, user_id, target_company: str | None) -> list[dict]:
    if not target_company:
        return []
    result = await db.execute(
        select(CompanyNote).where(CompanyNote.user_id == user_id).where(CompanyNote.company.ilike(target_company))
    )
    return [{"company": n.company, "notes": n.pasted_content} for n in result.scalars().all()]


async def _get_leetcode_evidence(db: AsyncSession, user_id) -> dict | None:
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.user_id == user_id)
        .where(ProfileSnapshot.note.in_(["leetcode sync", "leetcode manual submission"]))
        .order_by(ProfileSnapshot.taken_at.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None or not isinstance(snapshot.skills_json, dict):
        return None

    stats = snapshot.skills_json.get("stats", {})
    insights = snapshot.skills_json.get("insights", {})
    topic_mastery = insights.get("topic_mastery", [])

    mastery_order = {
        "Extensive Practice": 0, "Consistent Practice": 1,
        "Some Practice": 2, "Introduced": 3, "Not Practiced": 4,
    }
    top_topics = sorted(
        [t for t in topic_mastery if t["problems"] > 0],
        key=lambda t: (mastery_order.get(t["mastery"], 5), -t["problems"]),
    )[:5]

    return {
        "total_solved": stats.get("total_solved", 0),
        "easy": stats.get("easy", 0),
        "medium": stats.get("medium", 0),
        "hard": stats.get("hard", 0),
        "top_topics": [{"topic": t["topic"], "mastery": t["mastery"], "problems": t["problems"]} for t in top_topics],
        "blind_spots": insights.get("blind_spots", {}).get("missing_fundamentals", []),
    }


async def _get_target_job_intelligence(db: AsyncSession, job_intelligence_id: str | None) -> dict | None:
    if not job_intelligence_id:
        return None
    profile = await get_job_intelligence(db, UUID(job_intelligence_id))
    if profile is None:
        return None
    return {
        "role": profile.role,
        "company": profile.company,
        "seniority_signal": profile.seniority_signal.model_dump(),
        "interview_focus_areas": profile.interview_focus_areas,
        "required_technologies": profile.all_required_technologies,
    }


async def _get_recent_conversation_turns(
    db: AsyncSession, user_id, session_id: str | None, limit: int = MAX_CONVERSATION_TURNS
) -> list[dict]:
    if not session_id:
        return []
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        return []

    result = await db.execute(
        select(InterviewResponse)
        .where(InterviewResponse.user_id == user_id)
        .where(InterviewResponse.session_id == session_uuid)
        .order_by(InterviewResponse.created_at.desc())
        .limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    turns = []
    for r in rows:
        rj = r.response_json or {}
        turns.append({"question": r.question, "answer_short": rj.get("answer_short", "")})
    return turns


async def _get_github_repo_evidence(db: AsyncSession, user_id, limit: int = 6) -> list[dict]:
    result = await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)
    )
    eligible = [
        a for a in result.scalars().all()
        if not (a.is_fork and not a.is_meaningful_fork_contribution)
    ]
    ranked = sorted(eligible, key=lambda a: a.quality_score * 0.6 + a.activity_score * 0.4, reverse=True)

    return [
        {
            "type": "github_repo",
            "name": a.repo_name,
            "category": a.category,
            "technologies": a.technologies,
            "capabilities": a.capabilities,
            "tier": a.tier,
            "quality_score": a.quality_score,
            "activity_score": a.activity_score,
            "has_tests": a.has_tests,
            "has_ci": a.has_ci,
            "commit_hygiene_score": a.commit_hygiene_score,
            "collaboration_mode": a.collaboration_mode,
            "architecture_depth": (a.architecture_assessment or {}).get("depth_label"),
        }
        for a in ranked[:limit]
    ]


async def build_interview_context(
    db: AsyncSession,
    user_id,
    question: str,
    target_role: str | None,
    target_company: str | None,
    job_intelligence_id: str | None = None,
    session_id: str | None = None,
    correction: str | None = None,
    blueprint_key: str | None = None,
) -> dict:
    """`blueprint_key` — the ALREADY-classified blueprint for this
    question (see response_generation.classify_blueprint, now called by
    the API layer BEFORE this function so retrieval can use its
    competency hints — see api/interview.py). Optional only so this
    function still has a sane default (no competency bonus) if a caller
    genuinely doesn't have one yet; every real call site passes it.
    """
    target_job_intelligence = await _get_target_job_intelligence(db, job_intelligence_id)
    required_technologies = set(target_job_intelligence["required_technologies"]) if target_job_intelligence else set()
    competency_hints = get_blueprint_competency_hints(blueprint_key) if blueprint_key else set()

    confidence_by_canonical = await _get_confidence_map(db, user_id)
    skills = _slim_skills(confidence_by_canonical)

    project_rows = await _load_projects_with_tags(db, user_id)
    experience_rows = await _load_experiences_with_tags(db, user_id)

    raw_stack_strings: set[str] = set()
    for p in project_rows:
        raw_stack_strings.update(p.stack or [])
    for e in experience_rows:
        raw_stack_strings.update(e.stack or [])
    canonical_by_raw = await resolve_skills(raw_stack_strings, db) if raw_stack_strings else {}

    projects = _rank_and_cap(
        project_rows,
        stack_of=lambda p: p.stack,
        tags_of=lambda p: p.competency_tags,
        to_dict=lambda p: {
            "type": "project", "name": p.name, "description": p.description or "", "stack": p.stack or [],
        },
        competency_hints=competency_hints,
        required_technologies=required_technologies,
        canonical_by_raw=canonical_by_raw,
        confidence_by_canonical=confidence_by_canonical,
        max_items=MAX_PROJECTS_IN_CONTEXT,
    )
    experiences = _rank_and_cap(
        experience_rows,
        stack_of=lambda e: e.stack,
        tags_of=lambda e: e.competency_tags,
        to_dict=lambda e: {
            "type": "experience",
            "label": f"{e.role} at {e.company}",
            "role": e.role,
            "company": e.company,
            "start_date": e.start_date.isoformat() if e.start_date else None,
            "end_date": e.end_date.isoformat() if e.end_date else None,
            "bullets": e.bullets or [],
            "stack": e.stack or [],
        },
        competency_hints=competency_hints,
        required_technologies=required_technologies,
        canonical_by_raw=canonical_by_raw,
        confidence_by_canonical=confidence_by_canonical,
        max_items=MAX_EXPERIENCES_IN_CONTEXT,
    )

    education = await _get_all_education(db, user_id)
    github_repos = await _get_github_repo_evidence(db, user_id)
    leetcode_evidence = await _get_leetcode_evidence(db, user_id)
    company_notes = await _get_company_notes(db, user_id, target_company)
    identity = await build_identity_context_for_interview(db, user_id)
    recent_conversation = await _get_recent_conversation_turns(db, user_id, session_id)

    return {
        "question": question,
        "target_role": target_role,
        "target_company": target_company,
        "target_job_intelligence": target_job_intelligence,
        "identity": identity,
        "recent_conversation": recent_conversation,
        "correction": correction,
        "profile": {
            "projects": projects,
            "experiences": experiences,
            "education": education,
            "skills": skills,
            "github_repos": github_repos,
            "leetcode_evidence": leetcode_evidence,
        },
        "company_notes": company_notes,
        "blueprint_library": get_blueprint_library(),
        "persona": get_persona(),
    }