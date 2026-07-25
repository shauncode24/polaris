from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.database import get_db
from app.models.goals import Goal
from app.models.inference import CareerPlan
from app.schemas.career_plan import CareerPlanResponse, GoalCreateRequest, GoalResponse
from app.services.career_planner.context_builder import build_career_plan_context
from app.services.career_planner.plan_generation import generate_career_plan
from app.services.user_helpers import get_or_create_default_user

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("", response_model=GoalResponse)
async def create_goal(payload: GoalCreateRequest, db=Depends(get_db)):
    user = await get_or_create_default_user(db)
    goal = Goal(
        user_id=user.id,
        title=payload.title,
        deadline=payload.deadline,
        priority=payload.priority,
        status_pct=0.0,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    print(f"[TRACING] Created goal '{goal.title}' (id={goal.id}, deadline={goal.deadline})", flush=True)
    return GoalResponse(
        id=str(goal.id), title=goal.title, deadline=goal.deadline,
        priority=goal.priority, status_pct=goal.status_pct, created_at=goal.created_at,
    )


@router.get("", response_model=list[GoalResponse])
async def list_goals(db=Depends(get_db)):
    user = await get_or_create_default_user(db)
    result = await db.execute(
        select(Goal).where(Goal.user_id == user.id).order_by(Goal.created_at.desc())
    )
    return [
        GoalResponse(
            id=str(g.id), title=g.title, deadline=g.deadline,
            priority=g.priority, status_pct=g.status_pct, created_at=g.created_at,
        )
        for g in result.scalars().all()
    ]


@router.post("/{goal_id}/plan", response_model=CareerPlanResponse)
async def generate_plan_for_goal(goal_id: UUID, db=Depends(get_db)):
    user = await get_or_create_default_user(db)

    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    context = await build_career_plan_context(db, user.id, goal)
    llm_output, degraded = await generate_career_plan(context)

    plan_row = CareerPlan(
        user_id=user.id,
        goal_id=goal.id,
        plan_json={
            "daily_plan": [d.model_dump() for d in llm_output.daily_plan],
            "check_ins": llm_output.check_ins,
            "days_available": context["days_available"],
            "degraded": degraded,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(plan_row)
    await db.commit()
    await db.refresh(plan_row)

    print(f"[TRACING] Career plan generated and persisted (plan_id={plan_row.id}, degraded={degraded})", flush=True)

    return CareerPlanResponse(
        plan_id=str(plan_row.id),
        goal_id=str(goal.id),
        days_available=context["days_available"],
        daily_plan=llm_output.daily_plan,
        check_ins=llm_output.check_ins,
        generated_at=plan_row.created_at,
        degraded=degraded,
    )