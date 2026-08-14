# backend/app/api/interview.py
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.database import get_db
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
    generate_interview_response,
)
from app.api.deps import get_current_user
from app.models.facts import User

router = APIRouter(prefix="/interview", tags=["interview"])


def _build_output(
    question: str,
    output,
    target_role: str | None,
    target_company: str | None,
    session_id: UUID,
    parent_response_id: UUID | None,
    correction_of: UUID | None = None,
    suggested_action: str | None = None,
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
        context_note=output.context_note,
        target_role=target_role,
        target_company=target_company,
        claims_needing_verification=output.claims_needing_verification,
        grounding=output.grounding,
        session_id=str(session_id),
        parent_response_id=str(parent_response_id) if parent_response_id else None,
        correction_of=str(correction_of) if correction_of else None,
        suggested_action=suggested_action,
    )


@router.post("/ask", response_model=InterviewResponseOutput)
async def ask_interview_question(payload: InterviewAskRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    print(f"[TRACING] Received interview question: {payload.question!r}", flush=True)
    user = current_user

    session_id = UUID(payload.session_id) if payload.session_id else uuid4()
    parent_response_id = UUID(payload.parent_response_id) if payload.parent_response_id else None

    context = await build_interview_context(
        db, user.id, payload.question, payload.target_role, payload.target_company,
        job_intelligence_id=payload.job_intelligence_id,
        session_id=str(session_id),
        correction=payload.correction,
    )

    try:
        output = await generate_interview_response(context)
    except InterviewGenerationError as e:
        print(f"[TRACING] Interview generation failed: {e}", flush=True)
        raise HTTPException(status_code=502, detail=str(e))

    output_full = _build_output(
        payload.question, output, payload.target_role, payload.target_company,
        session_id, parent_response_id,
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

    print(f"[TRACING] Interview response persisted (id={response_row.id}, session_id={session_id})", flush=True)

    output_full.response_id = str(response_row.id)
    output_full.created_at = response_row.created_at
    return output_full


@router.post("/correct", response_model=InterviewResponseOutput)
async def correct_interview_response(
    payload: CorrectionRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Re-asks the original question with the correction injected as a
    hard constraint (implementation plan §13). Never mutates
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

    context = await build_interview_context(
        db, current_user.id, parent.question, target_role, target_company,
        session_id=str(session_id),
        correction=payload.correction,
    )

    try:
        output = await generate_interview_response(context)
    except InterviewGenerationError as e:
        print(f"[TRACING] Interview correction generation failed: {e}", flush=True)
        raise HTTPException(status_code=502, detail=str(e))

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
        session_id, parent.id, correction_of=parent.id, suggested_action=suggested_action,
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

    print(f"[TRACING] Interview correction persisted (id={response_row.id}, corrects={parent.id})", flush=True)

    output_full.response_id = str(response_row.id)
    output_full.created_at = response_row.created_at
    return output_full


@router.get("/sessions", response_model=list[InterviewSessionSummary])
async def list_interview_sessions(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    """Recent interview practice sessions for this user, most recent
    first — grouped by session_id. A pre-migration row with no
    session_id becomes its own single-item session, so old history
    keeps rendering unchanged.
    """
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
    """Full ordered thread for one session — what the frontend needs to
    reconstruct a conversation view when the user selects a past session
    from history, since the summary list only returns one row per
    session. Not in the original implementation plan's endpoint list,
    but required for §15's session-grouped history to actually work.
    """
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