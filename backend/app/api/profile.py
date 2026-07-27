from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User, Experience, Project, Education

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/data")
async def get_profile_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the user's experiences, projects, and education records."""

    exp_result = await db.execute(
        select(Experience).where(Experience.user_id == current_user.id).order_by(Experience.start_date.desc().nullsfirst())
    )
    experiences = exp_result.scalars().all()

    proj_result = await db.execute(
        select(Project).where(Project.user_id == current_user.id).order_by(Project.created_at.desc())
    )
    projects = proj_result.scalars().all()

    edu_result = await db.execute(
        select(Education).where(Education.user_id == current_user.id).order_by(Education.end_date.desc().nullsfirst())
    )
    education = edu_result.scalars().all()

    return {
        "experiences": [
            {
                "id": str(e.id),
                "title": e.role,
                "company": e.company,
                "start_year": e.start_date.year if e.start_date else None,
                "end_year": e.end_date.year if e.end_date else None,
                "skills_used": e.stack or [],
                "description": (e.bullets[0] if e.bullets else None),
                "sources": ["resume"],
            }
            for e in experiences
        ],
        "projects": [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "skills_used": p.stack or [],
                "sources": ["resume"],
            }
            for p in projects
        ],
        "education": [
            {
                "id": str(e.id),
                "institution": e.institution,
                "degree": e.degree,
                "field_of_study": e.field_of_study,
                "graduation_year": e.end_date.year if e.end_date else None,
                "is_current": e.is_current,
            }
            for e in education
        ],
    }
