# backend/app/api/interview.py
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.database import get_db
from app.models.inference import InterviewResponse
from app.schemas.interview_response import (
    InterviewAskRequest,
    InterviewResponseOutput,
    InterviewSessionSummary,
)
from app.services.interview.context_builder import build_interview_context
from app.services.interview.response_generation import (
    InterviewGenerationError,
    generate_interview_response,
)
from app.api.deps import get_current_user
from app.models.facts import User

router = APIRouter(prefix="/interview", tags=["interview"])


@router.post("/ask", response_model=InterviewResponseOutput)
async def ask_interview_question(payload: InterviewAskRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    print(f"[TRACING] Received interview question: {payload.question!r}", flush=True)
    user = current_user

    context = await build_interview_context(
        db, user.id, payload.question, payload.target_role, payload.target_company,
    )

    try:
        output = await generate_interview_response(context)
    except InterviewGenerationError as e:
        print(f"[TRACING] Interview generation failed: {e}", flush=True)
        raise HTTPException(status_code=502, detail=str(e))

    output_full = InterviewResponseOutput(
        question=payload.question,
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
        target_role=payload.target_role,
        target_company=payload.target_company,
    )

    response_row = InterviewResponse(
        user_id=user.id,
        question=payload.question,
        question_type=output.question_type,
        response_json=output_full.model_dump(mode="json"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(response_row)
    await db.commit()
    await db.refresh(response_row)

    print(f"[TRACING] Interview response persisted (id={response_row.id})", flush=True)

    output_full.response_id = str(response_row.id)
    output_full.created_at = response_row.created_at
    return output_full


@router.get("/sessions", response_model=list[InterviewSessionSummary])
async def list_interview_sessions(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    """Recent interview practice sessions for this user, most recent first.
    target_role/target_company are read back from response_json (persisted
    on /ask) since InterviewResponse itself only stores question/type.
    """
    result = await db.execute(
        select(InterviewResponse)
        .where(InterviewResponse.user_id == current_user.id)
        .order_by(InterviewResponse.created_at.desc())
        .limit(30)
    )
    rows = result.scalars().all()
    summaries = []
    for r in rows:
        rj = r.response_json or {}
        summaries.append(
            InterviewSessionSummary(
                id=str(r.id),
                question=r.question,
                question_type=r.question_type,
                target_role=rj.get("target_role"),
                target_company=rj.get("target_company"),
                created_at=r.created_at,
            )
        )
    return summaries