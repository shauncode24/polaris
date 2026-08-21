# backend/app/api/career.py
from datetime import datetime, timezone
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.database import get_db, AsyncSessionLocal
from app.models.goals import Goal
from app.models.inference import CareerPlan
from app.models.facts import JobDescription
from app.schemas.career_planner.career_plan import (
    CareerPlanResponse, GoalCreateRequest, GoalUpdateRequest, GoalResponse, TopicSignal, TargetJobSummary,
)
from app.services.career_planner.context_builder import build_career_plan_context
from app.services.career_planner.plan_generation import generate_career_plan
from app.api.deps import get_current_user
from app.models.facts import User
from uuid import UUID as UUIDType

router = APIRouter(prefix="/goals", tags=["goals"])

logger = logging.getLogger(__name__)


def _build_check_ins(days_available: int) -> list[str]:
    if days_available < 5:
        return ["Final review day before the interview/deadline"]
    return [f"Day {d} check-in" for d in range(3, days_available + 1, 3)] + [
        "Final review day before the interview/deadline"
    ]


def _to_goal_response(goal: Goal) -> GoalResponse:
    return GoalResponse(
        id=str(goal.id), title=goal.title, deadline=goal.deadline,
        priority=goal.priority, status_pct=goal.status_pct, created_at=goal.created_at,
        job_description_id=str(goal.job_description_id) if goal.job_description_id else None,
    )


@router.post("", response_model=GoalResponse)
async def create_goal(payload: GoalCreateRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    user = current_user

    job_description_id = None
    if payload.job_description_id:
        try:
            candidate_id = UUIDType(payload.job_description_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid job_description_id.")
        jd_result = await db.execute(
            select(JobDescription).where(JobDescription.id == candidate_id, JobDescription.user_id == user.id)
        )
        jd = jd_result.scalar_one_or_none()
        if jd is None:
            raise HTTPException(status_code=404, detail="Analyzed job not found.")
        job_description_id = candidate_id

    goal = Goal(
        user_id=user.id,
        job_description_id=job_description_id,
        title=payload.title,
        deadline=payload.deadline,
        priority=payload.priority,
        status_pct=0.0,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    logger.info("Created goal '%s' (id=%s, deadline=%s)", goal.title, goal.id, goal.deadline)
    return _to_goal_response(goal)


@router.get("", response_model=list[GoalResponse])
async def list_goals(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    user = current_user
    result = await db.execute(
        select(Goal).where(Goal.user_id == user.id).order_by(Goal.created_at.desc())
    )
    return [_to_goal_response(g) for g in result.scalars().all()]


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: UUID, payload: GoalUpdateRequest,
    current_user: User = Depends(get_current_user), db=Depends(get_db),
):
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id))
    goal = result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    if payload.title is not None:
        goal.title = payload.title
    if payload.deadline is not None:
        goal.deadline = payload.deadline
    if payload.priority is not None:
        goal.priority = payload.priority

    await db.commit()
    await db.refresh(goal)
    return _to_goal_response(goal)


@router.delete("/{goal_id}")
async def delete_goal(goal_id: UUID, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id))
    goal = result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.delete(goal)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{goal_id}/plan", response_model=CareerPlanResponse)
async def generate_plan_for_goal(goal_id: UUID, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    user = current_user

    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    context = await build_career_plan_context(db, user.id, goal)
    await db.close()  # Release the connection back to the pool before starting slow LLM calls

    llm_output, degraded = await generate_career_plan(context)
    check_ins = _build_check_ins(context["days_available"])

    target_job_ctx = context.get("target_job")
    target_job_summary = (
        TargetJobSummary(
            role=target_job_ctx.get("role"),
            company=target_job_ctx.get("company"),
            overall_match_percentage=target_job_ctx.get("overall_match_percentage"),
            overall_match_label=target_job_ctx.get("overall_match_label"),
            missing_skills=[m["skill"] for m in target_job_ctx.get("missing_skills", []) if m.get("skill")],
            have_skills=target_job_ctx.get("have_skills", []),
        )
        if target_job_ctx else None
    )

    plan_row = CareerPlan(
        user_id=user.id,
        goal_id=goal.id,
        plan_json={
            "daily_plan": [d.model_dump() for d in llm_output.daily_plan],
            "check_ins": check_ins,
            "days_available": context["days_available"],
            "topic_signals": context["topic_signals"],
            "target_job": target_job_summary.model_dump() if target_job_summary else None,
            "degraded": degraded,
        },
        created_at=datetime.now(timezone.utc),
    )
    async with AsyncSessionLocal() as write_db:
        write_db.add(plan_row)
        await write_db.commit()
        await write_db.refresh(plan_row)

    logger.info(
        "Career plan generated and persisted (plan_id=%s, degraded=%s)", plan_row.id, degraded
    )

    return CareerPlanResponse(
        plan_id=str(plan_row.id),
        goal_id=str(goal.id),
        days_available=context["days_available"],
        relevant_domains=context.get("relevant_domains", []),
        daily_plan=llm_output.daily_plan,
        check_ins=check_ins,
        generated_at=plan_row.created_at,
        degraded=degraded,
        topic_signals=[TopicSignal(**t) for t in context["topic_signals"]],
        target_job=target_job_summary,
    )