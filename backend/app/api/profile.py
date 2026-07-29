from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User, Experience, Project, Education, Resume

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/data")
async def get_profile_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the user's experiences, projects, and education records."""

    from app.services.projects.linking import normalize_name

    exp_result = await db.execute(
        select(Experience)
        .where(Experience.user_id == current_user.id)
        .order_by(Experience.start_date.desc().nullsfirst(), Experience.created_at.desc())
    )
    all_experiences = exp_result.scalars().all()
    seen_exps = set()
    experiences = []
    for e in all_experiences:
        key = f"{normalize_name(e.role)}@{normalize_name(e.company)}"
        if key not in seen_exps:
            seen_exps.add(key)
            experiences.append(e)

    proj_result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    all_projects = proj_result.scalars().all()
    seen_projs = set()
    projects = []
    for p in all_projects:
        key = normalize_name(p.name)
        if key not in seen_projs:
            seen_projs.add(key)
            projects.append(p)

    edu_result = await db.execute(
        select(Education)
        .where(Education.user_id == current_user.id)
        .order_by(Education.end_date.desc().nullsfirst(), Education.created_at.desc())
    )
    all_education = edu_result.scalars().all()
    seen_edus = set()
    education = []
    for e in all_education:
        key = f"{normalize_name(e.institution)}@{normalize_name(e.degree or '')}"
        if key not in seen_edus:
            seen_edus.add(key)
            education.append(e)

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
