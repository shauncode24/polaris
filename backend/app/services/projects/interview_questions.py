import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.inference import ProjectInterviewQuestionsReview
from app.prompts.projects.project_interview_questions import PROJECT_INTERVIEW_QUESTIONS_SYSTEM_PROMPT
from app.schemas.projects.project_intelligence import (
    InterviewQuestionItem,
    InterviewQuestionsLLMOutput,
    InterviewQuestionsReport,
)


def _fallback_questions(project_context: dict) -> list[InterviewQuestionItem]:
    questions: list[InterviewQuestionItem] = []
    verified = project_context.get("verified", {}) or {}
    for tech in (verified.get("technologies") or [])[:3]:
        questions.append(InterviewQuestionItem(
            question=f"Why did you choose {tech} for this project, and what would you reconsider?",
            grounded_in=tech,
            difficulty="medium",
        ))
    if verified.get("has_tests") is False:
        questions.append(InterviewQuestionItem(
            question="This project doesn't show automated tests — how did you validate correctness?",
            grounded_in="no tests detected",
            difficulty="medium",
        ))
    if not questions:
        questions.append(InterviewQuestionItem(
            question=f"Walk me through the hardest technical decision in {project_context.get('name', 'this project')}.",
            grounded_in="project description",
            difficulty="medium",
        ))
    return questions[:5]


async def get_cached_interview_questions(db: AsyncSession, project_id) -> InterviewQuestionsReport | None:
    result = await db.execute(
        select(ProjectInterviewQuestionsReview).where(ProjectInterviewQuestionsReview.project_id == project_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return InterviewQuestionsReport.model_validate(row.report_json)


async def _persist_interview_questions(db: AsyncSession, user_id, project_id, report: InterviewQuestionsReport) -> None:
    payload = report.model_dump(mode="json")
    stmt = (
        pg_insert(ProjectInterviewQuestionsReview)
        .values(
            user_id=user_id, project_id=project_id, report_json=payload,
            created_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            constraint="uq_interview_questions_project",
            set_={"report_json": payload, "created_at": datetime.now(timezone.utc)},
        )
    )
    await db.execute(stmt)
    await db.commit()


async def generate_interview_questions(project_context: dict) -> InterviewQuestionsReport:
    """Pure generation — no DB access. Callers that want caching should
    use generate_and_cache_interview_questions() below.
    """
    degraded = False
    try:
        print(f"[TRACING] Requesting interview questions for '{project_context['name']}'...", flush=True)
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": PROJECT_INTERVIEW_QUESTIONS_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(project_context)},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw interview questions JSON:\n{content}", flush=True)
        parsed = InterviewQuestionsLLMOutput.model_validate(json.loads(content))
        questions = parsed.questions
        if not questions:
            raise ValueError("Empty questions list")
    except Exception as e:
        print(f"[TRACING] Interview question generation degraded, using fallback: {e}", flush=True)
        questions = _fallback_questions(project_context)
        degraded = True

    return InterviewQuestionsReport(
        project_name=project_context.get("name", ""),
        questions=questions,
        generated_at=datetime.now(timezone.utc).isoformat(),
        analysis_degraded=degraded,
    )


async def generate_and_cache_interview_questions(
    db: AsyncSession, user_id, project_id, project_context: dict
) -> InterviewQuestionsReport:
    report = await generate_interview_questions(project_context)
    await _persist_interview_questions(db, user_id, project_id, report)
    return report