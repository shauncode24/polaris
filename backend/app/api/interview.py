# backend/app/api/interview.py
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.database import get_db
from app.models.facts import JobDescription
from app.models.goals import Goal
from app.models.inference import InterviewResponse
from app.schemas.interview.interview_response import (
    CorrectionRequest,
    InterviewAskRequest,
    InterviewResponseOutput,
    InterviewSessionSummary,
)
from app.services.interview import grounding
from app.services.interview.context_builder import build_interview_context
from app.services.interview.response_generation import (
    InterviewGenerationError,
    classify_blueprint,
    generate_interview_response,
)
from app.api.deps import get_current_user
from app.models.facts import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview", tags=["interview"])


async def _auto_attach_job_intelligence_id(db, user_id) -> str | None:
    """Implementation plan §M — when the caller didn't pass an explicit
    job_intelligence_id, check whether the user has a real, active Goal
    with a job attached and use ITS job_intelligence_id instead of
    leaving the interview JD-blind. Deliberately narrow: only looks at
    the single soonest-due active goal that actually has a
    job_description_id AND whose JobDescription has actually been run
    through the Job Intelligence pipeline (job_intelligence_id set) —
    a legacy pre-refactor JobDescription with no job_intelligence_id is
    silently skipped rather than surfaced as a false match.
    """
    result = await db.execute(
        select(Goal)
        .where(Goal.user_id == user_id)
        .where(Goal.status_pct < 100.0)
        .where(Goal.job_description_id.isnot(None))
        .order_by(Goal.deadline.asc().nullslast())
        .limit(1)
    )
    goal = result.scalar_one_or_none()
    if goal is None:
        return None

    jd_result = await db.execute(
        select(JobDescription.job_intelligence_id).where(JobDescription.id == goal.job_description_id)
    )
    job_intelligence_id = jd_result.scalar_one_or_none()
    return str(job_intelligence_id) if job_intelligence_id else None


def _build_output(
    question: str,
    output,
    target_role: str | None,
    target_company: str | None,
    session_id: UUID,
    parent_response_id: UUID | None,
    trace_id: str,
    correction_of: UUID | None = None,
    suggested_action: str | None = None,
    auto_attached_job_intelligence_id: str | None = None,
) -> InterviewResponseOutput:
    return InterviewResponseOutput(
        question=question,
        question_type=output.question_type,
        blueprint_used=output.blueprint_used,
        answer=output.answer,
        answer_short=output.answer_short,
        stories_used=output.stories_used,
        competencies=output.competencies,
        follow_up_questions=output.follow_up_questions,
        coaching=output.coaching,
        insufficient_context=output.insufficient_context,
        insufficient_context_reason=output.insufficient_context_reason,
        context_note=output.context_note,
        target_role=target_role,
        target_company=target_company,
        claims_needing_verification=output.claims_needing_verification,
        grounding=output.grounding,
        session_id=str(session_id),
        parent_response_id=str(parent_response_id) if parent_response_id else None,
        correction_of=str(correction_of) if correction_of else None,
        suggested_action=suggested_action,
        trace_id=trace_id,
        auto_attached_job_intelligence_id=auto_attached_job_intelligence_id,
    )


def _degraded_error_detail(trace_id: str, message: str) -> dict:
    return {"error_type": "generation_degraded", "message": message, "trace_id": trace_id}


@router.post("/ask", response_model=InterviewResponseOutput)
async def ask_interview_question(payload: InterviewAskRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    trace_id = str(uuid4())
    logger.info("[trace=%s] Received interview question: %r", trace_id, payload.question)
    user = current_user

    session_id = UUID(payload.session_id) if payload.session_id else uuid4()
    parent_response_id = UUID(payload.parent_response_id) if payload.parent_response_id else None

    job_intelligence_id = payload.job_intelligence_id
    auto_attached_job_intelligence_id = None
    if not job_intelligence_id:
        auto_attached_job_intelligence_id = await _auto_attach_job_intelligence_id(db, user.id)
        job_intelligence_id = auto_attached_job_intelligence_id
        if auto_attached_job_intelligence_id:
            logger.info(
                "[trace=%s] auto-attached job_intelligence_id=%s from active goal",
                trace_id, auto_attached_job_intelligence_id,
            )

    # Classification happens BEFORE context is built so retrieval's
    # competency-hint ranking (context_builder.py) can actually use it.
    blueprint_key = await classify_blueprint(payload.question, trace_id=trace_id)

    context = await build_interview_context(
        db, user.id, payload.question, payload.target_role, payload.target_company,
        job_intelligence_id=job_intelligence_id,
        session_id=str(session_id),
        correction=payload.correction,
        blueprint_key=blueprint_key,
    )

    try:
        output = await generate_interview_response(context, blueprint_key, trace_id=trace_id)
    except InterviewGenerationError as e:
        logger.warning("[trace=%s] Interview generation failed: %s", trace_id, e)
        raise HTTPException(status_code=502, detail=_degraded_error_detail(trace_id, str(e)))

    output_full = _build_output(
        payload.question, output, payload.target_role, payload.target_company,
        session_id, parent_response_id, trace_id,
        auto_attached_job_intelligence_id=auto_attached_job_intelligence_id,
    )

    response_row = InterviewResponse(
        user_id=user.id,
        question=payload.question,
        question_type=output.question_type,
        response_json=output_full.model_dump(mode="json"),
        session_id=session_id,
        parent_response_id=parent_response_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(response_row)
    await db.commit()
    await db.refresh(response_row)

    logger.info("[trace=%s] Interview response persisted (response_id=%s, session_id=%s)", trace_id, response_row.id, session_id)

    output_full.response_id = str(response_row.id)
    output_full.created_at = response_row.created_at
    return output_full


@router.post("/correct", response_model=InterviewResponseOutput)
async def correct_interview_response(
    payload: CorrectionRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Re-plans and re-generates the original question with the
    correction injected as a hard constraint at BOTH the plan stage
    (so a corrected fact never gets cited/planned in the first place)
    and the prose stage (as a final wording safety net). Never mutates
    Experience/Project/SkillEvidence/EngineeringIdentity — corrections
    are conversational-scope only. When the correction looks like it
    fixes a durable fact (role/ownership/scope language), the response
    carries a plain-language 'suggested_action' pointing the user to the
    real first-class edit path instead.
    """
    trace_id = str(uuid4())

    try:
        parent_id = UUID(payload.parent_response_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid parent_response_id.")

    result = await db.execute(
        select(InterviewResponse).where(
            InterviewResponse.id == parent_id,
            InterviewResponse.user_id == current_user.id,
        )
    )
    parent = result.scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=404, detail="Original response not found.")

    parent_rj = parent.response_json or {}
    target_role = parent_rj.get("target_role")
    target_company = parent_rj.get("target_company")
    session_id = parent.session_id or uuid4()

    blueprint_key = await classify_blueprint(parent.question, trace_id=trace_id)

    context = await build_interview_context(
        db, current_user.id, parent.question, target_role, target_company,
        session_id=str(session_id),
        correction=payload.correction,
        blueprint_key=blueprint_key,
    )

    try:
        output = await generate_interview_response(context, blueprint_key, trace_id=trace_id)
    except InterviewGenerationError as e:
        logger.warning("[trace=%s] Interview correction generation failed: %s", trace_id, e)
        raise HTTPException(status_code=502, detail=_degraded_error_detail(trace_id, str(e)))

    suggested_action = None
    if grounding.looks_like_durable_correction(payload.correction):
        suggested_action = (
            "This looks like it corrects a durable fact about your background (e.g. a role or "
            "ownership claim) rather than just this answer's wording. This correction only updates "
            "this conversation — to fix it everywhere, edit the underlying entry on the Resume or "
            "Projects page (or add context via Company Notes if it's about how you'd frame this for "
            "a specific company)."
        )

    output_full = _build_output(
        parent.question, output, target_role, target_company,
        session_id, parent.id, trace_id, correction_of=parent.id, suggested_action=suggested_action,
    )

    response_row = InterviewResponse(
        user_id=current_user.id,
        question=parent.question,
        question_type=output.question_type,
        response_json=output_full.model_dump(mode="json"),
        session_id=session_id,
        parent_response_id=parent.id,
        correction_of=parent.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(response_row)
    await db.commit()
    await db.refresh(response_row)

    logger.info("[trace=%s] Interview correction persisted (response_id=%s, corrects=%s)", trace_id, response_row.id, parent.id)

    output_full.response_id = str(response_row.id)
    output_full.created_at = response_row.created_at
    return output_full


@router.get("/sessions", response_model=list[InterviewSessionSummary])
async def list_interview_sessions(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(
        select(InterviewResponse)
        .where(InterviewResponse.user_id == current_user.id)
        .order_by(InterviewResponse.created_at.desc())
        .limit(200)
    )
    rows = list(result.scalars().all())

    sessions: dict[str, list[InterviewResponse]] = {}
    for r in rows:
        key = str(r.session_id) if r.session_id else f"row:{r.id}"
        sessions.setdefault(key, []).append(r)

    summaries = []
    for group in sessions.values():
        latest = group[0]
        earliest = group[-1]
        rj = latest.response_json or {}
        summaries.append(InterviewSessionSummary(
            id=str(latest.id),
            question=earliest.question,
            question_type=latest.question_type,
            target_role=rj.get("target_role"),
            target_company=rj.get("target_company"),
            created_at=latest.created_at,
            session_id=str(latest.session_id) if latest.session_id else None,
        ))

    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return summaries[:30]

@router.get("/sessions/{session_id}")
async def get_interview_session_thread(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(
        select(InterviewResponse)
        .where(InterviewResponse.user_id == current_user.id)
        .where(InterviewResponse.session_id == session_id)
        .order_by(InterviewResponse.created_at.asc())
    )
    rows = list(result.scalars().all())
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found.")
    return [r.response_json for r in rows]