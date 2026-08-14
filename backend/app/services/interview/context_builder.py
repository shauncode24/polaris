"""Gathers the candidate's ENTIRE real profile as-is, plus the static
blueprint library and persona config, and hands all of it to the LLM
untouched. No scoring, no filtering of WHICH stories/evidence to use —
the model still decides that, not this module.

TOKEN BUDGET FIX: this module previously sent the full, un-slimmed
reconciled skill list (every individual evidence source string per
skill, unbounded count) AND a byte-for-byte duplicate of
identity.claim_risk_details under profile.project_claim_flags. Combined
with a duplicate-project bug elsewhere in the codebase (two Project rows
for the same conceptual project each carrying their own Claim Audit
finding), a real profile could push a single request well past Groq's
TPM limit (see the 413 "Request too large" failure this fixes). Nothing
here got smarter — the same real facts are still sent, just once each,
and without repeating the same evidence label dozens of times per skill.

Engineering Identity integration (implementation plan §3/§5): the
framing/self-knowledge layer (top_skills summary, role_fit,
engineering_quadrant, company_readiness, claim_risk_details,
coverage_gaps, evidence_coverage) is sourced from the single shared
identity_context adapter — see identity_context.py for the interview-
specific slimming applied there (dedup, dropped unused fields).

Raw narrative content (projects, experiences, education, github repos,
leetcode) is still fetched directly and IN FULL, since IdentityFacts
deliberately doesn't carry that granularity and the model genuinely
needs it to write a real answer.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import CompanyNote, Education, Experience, Project
from app.models.inference import InterviewResponse, ProfileSnapshot
from app.services.interview.blueprints import get_blueprint_library, get_persona
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.identity.identity_context import build_identity_context_for_interview
from app.services.identity.reconciled_confidence import get_reconciled_skill_confidences

from app.services.projects.linking import normalize_name

from app.models.github_analysis import GithubProjectAnalysis

MAX_CONVERSATION_TURNS = 6

# Token-budget caps for profile.skills / profile.education. The full
# reconciled skill list and the (occasionally duplicated) education list
# are otherwise unbounded — see module docstring for why these two were
# the largest contributors to the 413 this fixes.
MAX_SKILLS_IN_CONTEXT = 25
MAX_EDUCATION_IN_CONTEXT = 4


async def _get_all_projects(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
    )
    all_p = result.scalars().all()
    seen = set()
    projects = []
    for p in all_p:
        norm = normalize_name(p.name)
        if norm not in seen:
            seen.add(norm)
            projects.append({"type": "project", "name": p.name, "description": p.description or "", "stack": p.stack or []})
    return projects


async def _get_all_experiences(db: AsyncSession, user_id) -> list[dict]:
    result = await db.execute(
        select(Experience)
        .where(Experience.user_id == user_id)
        .order_by(Experience.start_date.desc().nullsfirst(), Experience.created_at.desc())
    )
    all_e = result.scalars().all()
    seen = set()
    experiences = []
    for e in all_e:
        key = f"{normalize_name(e.role)}@{normalize_name(e.company)}"
        if key not in seen:
            seen.add(key)
            experiences.append({
                "type": "experience",
                "label": f"{e.role} at {e.company}",
                "role": e.role,
                "company": e.company,
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "end_date": e.end_date.isoformat() if e.end_date else None,
                "bullets": e.bullets or [],
                "stack": e.stack or [],
            })
    return experiences


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
    # Cap rather than perfect the dedup above — a resume-driven
    # institution can still show up more than once with slightly
    # different degree/field phrasing across re-uploads; capping bounds
    # the size regardless of exactly how many near-duplicates exist.
    return education[:MAX_EDUCATION_IN_CONTEXT]


async def _get_all_skills_reconciled(db: AsyncSession, user_id) -> list[dict]:
    """Reconciled skill list for the prompt, SLIMMED to skill + confidence
    only. The full per-skill evidence list (every individual project/
    GitHub/experience label backing that skill — potentially 20+ strings
    for a broadly-used skill like "javascript") is dropped entirely: the
    prompt only ever needs to trust the confidence number as given (it
    says so explicitly — "already-reconciled ... Trust it as-is"), and
    it cites real stories by name from profile.projects/experiences/
    github_repos directly, never by walking a skill's evidence list.

    Capped to the MAX_SKILLS_IN_CONTEXT highest-confidence skills so a
    profile with a long low-value tail (individual LeetCode topic tags
    at confidence 0.1-0.2, for example) doesn't inflate the payload for
    no real signal.
    """
    reconciled = await get_reconciled_skill_confidences(db, user_id)
    ranked = sorted(reconciled.values(), key=lambda e: e["confidence"], reverse=True)
    return [
        {"skill": e["skill"], "confidence": e["confidence"]}
        for e in ranked[:MAX_SKILLS_IN_CONTEXT]
    ]


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
    """Last N {question, answer_short} pairs for this session, oldest
    first — purely for the model's own continuity ("as I mentioned
    earlier..."). Never re-fetches or embeds Identity data; this is
    conversation-scope memory only (implementation plan §12), never a
    separate memory store — it just reads back the same InterviewResponse
    rows.
    """
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


async def build_interview_context(
    db: AsyncSession,
    user_id,
    question: str,
    target_role: str | None,
    target_company: str | None,
    job_intelligence_id: str | None = None,
    session_id: str | None = None,
    correction: str | None = None,
) -> dict:
    projects = await _get_all_projects(db, user_id)
    experiences = await _get_all_experiences(db, user_id)
    education = await _get_all_education(db, user_id)
    skills = await _get_all_skills_reconciled(db, user_id)
    github_repos = await _get_github_repo_evidence(db, user_id)
    leetcode_evidence = await _get_leetcode_evidence(db, user_id)
    company_notes = await _get_company_notes(db, user_id, target_company)
    target_job_intelligence = await _get_target_job_intelligence(db, job_intelligence_id)
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
            # NOTE: claim-risk flags are NOT duplicated here anymore.
            # identity["claim_risk_details"] (already deduped by
            # identity_context.py) is the single copy of this data — see
            # STEP 0 / STEP 3 of the interview prompt, which now reads
            # from identity.claim_risk_details directly instead of a
            # second profile.project_claim_flags copy of the same facts.
        },
        "company_notes": company_notes,
        "blueprint_library": get_blueprint_library(),
        "persona": get_persona(),
    }


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