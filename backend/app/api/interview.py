from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db
from app.models.inference import InterviewResponse
from app.schemas.interview_response import InterviewAskRequest, InterviewResponseOutput
from app.services.interview.context_builder import build_interview_context
from app.services.interview.response_generation import (
    InterviewGenerationError,
    generate_interview_response,
)
from app.services.user_helpers import get_or_create_default_user

router = APIRouter(prefix="/interview", tags=["interview"])


@router.post("/ask", response_model=InterviewResponseOutput)
async def ask_interview_question(payload: InterviewAskRequest, db=Depends(get_db)):
    print(f"[TRACING] Received interview question: {payload.question!r}", flush=True)
    user = await get_or_create_default_user(db)

    context = await build_interview_context(
        db, user.id, payload.question, payload.target_role, payload.target_company,
    )

    try:
        output = await generate_interview_response(context)
    except InterviewGenerationError as e:
        print(f"[TRACING] Interview generation failed: {e}", flush=True)
        raise HTTPException(status_code=502, detail=str(e))

    response_row = InterviewResponse(
        user_id=user.id,
        question=payload.question,
        question_type=output.question_type,
        response_json=output.model_dump(mode="json"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(response_row)
    await db.commit()
    await db.refresh(response_row)

    print(f"[TRACING] Interview response persisted (id={response_row.id})", flush=True)

    return InterviewResponseOutput(
        response_id=str(response_row.id),
        question=payload.question,
        question_type=output.question_type,
        answer=output.answer,
        answer_short=output.answer_short,
        stories_used=output.stories_used,
        competencies=output.competencies,
        follow_up_questions=output.follow_up_questions,
        coaching=output.coaching,
        insufficient_context=output.insufficient_context,
        context_note=output.context_note,
        created_at=response_row.created_at,
    )