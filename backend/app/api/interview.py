# backend/app/api/interview.py
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.goals import Goal
from app.models.inference import InterviewResponse
from app.schemas.interview.interview_response import (
    CorrectionRequest,
    InterviewAskRequest,
    InterviewResponseOutput,
    InterviewSessionSummary,
)
from app.schemas.interview.practice import KitProgress, PracticeAnswer, PracticeAttemptView
from app.services.interview import grounding, practice
from app.services.interview.context_builder import build_interview_context
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.job_intelligence.library import get_primary_job_id
from app.services.interview.response_generation import (
    InterviewGenerationError,
    classify_blueprint,
    generate_interview_response,
)
from app.api.background_jobs import run_in_background
from app.api.deps import get_current_user
from app.models.facts import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview", tags=["interview"])


async def _goal_job_id(db, user_id) -> UUID | None:
    """The job attached to the user's soonest-due active goal."""
    result = await db.execute(
        select(Goal.job_intelligence_id)
        .where(Goal.user_id == user_id)
        .where(Goal.status_pct < 100.0)
        .where(Goal.job_intelligence_id.isnot(None))
        .order_by(Goal.deadline.asc().nullslast())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _names_another_job(job, target_role: str | None, target_company: str | None) -> bool:
    """True when the caller asked to practise for a different role or company
    than this job's.
    """
    return any(
        wanted and wanted.strip().lower() != (actual or "").strip().lower()
        for wanted, actual in ((target_role, job.role), (target_company, job.company))
    )


async def _auto_attach_job(db, user_id, target_role: str | None, target_company: str | None):
    """When the caller didn't name a job, use the one the user is preparing
    for: their primary target, otherwise their active goal's job. Neither is
    used if the caller typed a different role or company. Returns
    (job, "primary" | "goal"), or (None, None).
    """
    for source, find in (("primary", get_primary_job_id), ("goal", _goal_job_id)):
        job_id = await find(db, user_id)
        if job_id is None:
            continue
        job = await get_job_intelligence(db, user_id, job_id)
        if job is not None and not _names_another_job(job, target_role, target_company):
            return job, source
    return None, None


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
    job_intelligence_id: str | None = None,
    job_context_source: str | None = None,
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
        job_intelligence_id=job_intelligence_id,
        auto_attached_job_intelligence_id=job_intelligence_id if job_context_source else None,
        job_context_source=job_context_source,
        prompt_version=getattr(output, "prompt_version", None) or None,
    )


def _degraded_error_detail(trace_id: str, message: str) -> dict:
    return {"error_type": "generation_degraded", "message": message, "trace_id": trace_id}


@router.post("/ask", response_model=InterviewResponseOutput)
async def ask_interview_question(payload: InterviewAskRequest, current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    try:
        session_id = UUID(payload.session_id) if payload.session_id else uuid4()
        parent_response_id = UUID(payload.parent_response_id) if payload.parent_response_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id or parent_response_id.")

    async def work(job_db: AsyncSession):
        return await _answer_question(job_db, user_id, payload, session_id, parent_response_id)

    return await run_in_background(user_id, "interview_answer", work, inputs=(payload.model_dump(mode="json"),))


async def _answer_question(
    db: AsyncSession, user_id, payload: InterviewAskRequest, session_id: UUID, parent_response_id: UUID | None,
) -> InterviewResponseOutput:
    trace_id = str(uuid4())
    logger.info("[trace=%s] Received interview question: %r", trace_id, payload.question)

    job_intelligence_id = payload.job_intelligence_id
    job_context_source = None
    target_role, target_company = payload.target_role, payload.target_company
    if not job_intelligence_id:
        job, job_context_source = await _auto_attach_job(db, user_id, target_role, target_company)
        if job is not None:
            job_intelligence_id = job.id
            target_role = target_role or job.role
            target_company = target_company or job.company
            logger.info(
                "[trace=%s] auto-attached job_intelligence_id=%s (%s)", trace_id, job.id, job_context_source,
            )

    # Classification happens BEFORE context is built so retrieval's
    # competency-hint ranking (context_builder.py) can actually use it.
    blueprint_key = await classify_blueprint(payload.question, trace_id=trace_id)

    context = await build_interview_context(
        db, user_id, payload.question, target_role, target_company,
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
        payload.question, output, target_role, target_company,
        session_id, parent_response_id, trace_id,
        job_intelligence_id=job_intelligence_id, job_context_source=job_context_source,
    )

    response_row = InterviewResponse(
        user_id=user_id,
        question=payload.question,
        question_type=output.question_type,
        response_json=output_full.model_dump(mode="json"),
        session_id=session_id,
        parent_response_id=parent_response_id,
        prompt_version=output_full.prompt_version or None,
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
    try:
        parent_id = UUID(payload.parent_response_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid parent_response_id.")

    user_id = current_user.id
    parent = await _find_response(db, user_id, parent_id)

    async def work(job_db: AsyncSession):
        return await _rewrite_answer(job_db, user_id, parent.id, payload.correction)

    return await run_in_background(
        user_id, "interview_correction", work, inputs=(parent_id, payload.correction),
    )


async def _find_response(db: AsyncSession, user_id, response_id: UUID) -> InterviewResponse:
    result = await db.execute(
        select(InterviewResponse).where(
            InterviewResponse.id == response_id,
            InterviewResponse.user_id == user_id,
        )
    )
    response = result.scalar_one_or_none()
    if response is None:
        raise HTTPException(status_code=404, detail="Original response not found.")
    return response


async def _rewrite_answer(db: AsyncSession, user_id, parent_id: UUID, correction: str) -> InterviewResponseOutput:
    trace_id = str(uuid4())
    parent = await _find_response(db, user_id, parent_id)
    parent_rj = parent.response_json or {}
    target_role = parent_rj.get("target_role")
    target_company = parent_rj.get("target_company")
    session_id = parent.session_id or uuid4()
    # A correction rewrites the answer for the same job it was written for.
    # (Responses saved before `job_intelligence_id` only recorded auto-attached ones.)
    job_intelligence_id = (
        parent_rj.get("job_intelligence_id") or parent_rj.get("auto_attached_job_intelligence_id")
    )
    job_context_source = parent_rj.get("job_context_source")

    blueprint_key = await classify_blueprint(parent.question, trace_id=trace_id)

    context = await build_interview_context(
        db, user_id, parent.question, target_role, target_company,
        job_intelligence_id=job_intelligence_id,
        session_id=str(session_id),
        correction=correction,
        blueprint_key=blueprint_key,
    )

    try:
        output = await generate_interview_response(context, blueprint_key, trace_id=trace_id)
    except InterviewGenerationError as e:
        logger.warning("[trace=%s] Interview correction generation failed: %s", trace_id, e)
        raise HTTPException(status_code=502, detail=_degraded_error_detail(trace_id, str(e)))

    suggested_action = None
    if grounding.looks_like_durable_correction(correction):
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
        job_intelligence_id=job_intelligence_id, job_context_source=job_context_source,
    )

    response_row = InterviewResponse(
        user_id=user_id,
        question=parent.question,
        question_type=output.question_type,
        response_json=output_full.model_dump(mode="json"),
        session_id=session_id,
        parent_response_id=parent.id,
        correction_of=parent.id,
        prompt_version=output_full.prompt_version or None,
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


_QUESTION_NOT_FOUND = "Question not found."


@router.post("/questions/{question_id}/attempts", response_model=PracticeAttemptView)
async def practise_question(
    question_id: UUID,
    payload: PracticeAnswer,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Reviews the user's answer to a question of one of their interview kits."""
    user_id = current_user.id
    if await practice.find_question(db, user_id, question_id) is None:
        raise HTTPException(status_code=404, detail=_QUESTION_NOT_FOUND)

    async def work(job_db: AsyncSession):
        attempt = await practice.review_answer(job_db, user_id, question_id, payload.answer)
        if attempt is None:  # the question was deleted meanwhile
            raise HTTPException(status_code=404, detail=_QUESTION_NOT_FOUND)
        return attempt

    # Not refused when the day's AI calls are used up: the answer is still saved
    # and checked against the record, and says it has no score.
    return await run_in_background(
        user_id, "practice_review", work, inputs=(question_id, payload.answer), needs_model=False,
    )


@router.get("/questions/{question_id}/attempts", response_model=list[PracticeAttemptView])
async def list_practice_attempts(
    question_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    attempts = await practice.list_attempts(db, current_user.id, question_id)
    if attempts is None:
        raise HTTPException(status_code=404, detail=_QUESTION_NOT_FOUND)
    return attempts


@router.get("/kits/{job_intelligence_id}/progress", response_model=KitProgress)
async def get_practice_progress(
    job_intelligence_id: UUID,
    version: int | None = Query(None, ge=1),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    progress = await practice.kit_progress(db, current_user.id, job_intelligence_id, version)
    if progress is None:
        raise HTTPException(status_code=404, detail="Interview kit not found.")
    return progress
