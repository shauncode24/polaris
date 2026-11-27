"""The user's evidence record: what Polaris knows about them, where each
piece came from, and the controls to confirm, edit or hide it.
"""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import Education, Experience, Project, User
from app.services.evidence.confidence import get_hidden_skill_names, get_reconciled_skill_confidences
from app.services.evidence.review import (
    KINDS,
    ReviewError,
    apply_review,
    dedupe_rows,
    set_skill_hidden,
)
from app.services.evidence.scoring import label_for_confidence
from app.services.projects.linking import suggest_repo_links

router = APIRouter(prefix="/profile", tags=["profile"])

# Where a project's evidence came from, in terms the user recognises.
_PROJECT_SOURCES = {"resume": ["resume"], "github": ["github"], "both": ["resume", "github"]}


def _review_fields(row) -> dict:
    return {"review_state": row.review_state, "is_hidden": row.is_hidden}


def _experience_item(e: Experience) -> dict:
    return {
        "id": str(e.id),
        "title": e.role,
        "company": e.company,
        "start_year": e.start_date.year if e.start_date else None,
        "end_year": e.end_date.year if e.end_date else None,
        "skills_used": e.stack or [],
        "bullets": e.bullets or [],
        "description": (e.bullets[0] if e.bullets else None),
        "sources": [e.source or "resume"],
        **_review_fields(e),
    }


def _project_item(p: Project) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "skills_used": p.stack or [],
        "sources": _PROJECT_SOURCES.get(p.source or "resume", ["resume"]),
        "repo": (
            {"name": p.github_repo_name, "url": p.repo_url, "link_status": p.repo_link_status}
            if p.github_repo_name else None
        ),
        **_review_fields(p),
    }


def _education_item(e: Education) -> dict:
    return {
        "id": str(e.id),
        "institution": e.institution,
        "degree": e.degree,
        "field_of_study": e.field_of_study,
        "graduation_year": e.end_date.year if e.end_date else None,
        "is_current": e.is_current,
        "sources": [e.source or "resume"],
        **_review_fields(e),
    }


_SERIALIZERS = {"projects": _project_item, "experiences": _experience_item, "education": _education_item}


@router.get("/data")
async def get_profile_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The evidence record. Items the user hid are included (flagged
    `is_hidden`) so they can be restored; every other feature leaves them out.
    """
    uid = current_user.id

    experiences = dedupe_rows("experiences", list((await db.execute(
        select(Experience).where(Experience.user_id == uid)
        .order_by(Experience.start_date.desc().nullsfirst(), Experience.created_at.desc())
    )).scalars().all()))

    projects = dedupe_rows("projects", list((await db.execute(
        select(Project).where(Project.user_id == uid).order_by(Project.created_at.desc())
    )).scalars().all()))

    education = dedupe_rows("education", list((await db.execute(
        select(Education).where(Education.user_id == uid)
        .order_by(Education.end_date.desc().nullsfirst(), Education.created_at.desc())
    )).scalars().all()))

    reconciled = await get_reconciled_skill_confidences(db, uid)
    skills = [
        {
            "skill": entry["skill"],
            "confidence": entry["confidence"],
            "label": label_for_confidence(entry["confidence"]),
            "sources": entry["sources"],
            "corroboration_count": entry["corroboration_count"],
            "confidence_flags": entry["confidence_flags"],
            "is_hidden": False,
        }
        for entry in sorted(reconciled.values(), key=lambda e: e["confidence"], reverse=True)
    ]
    skills += [
        {"skill": name, "is_hidden": True} for name in sorted(await get_hidden_skill_names(db, uid))
    ]

    # Resume projects that look like a GitHub repo but not exactly: the user
    # confirms or ignores each one. (Exact matches are linked automatically.)
    visible_project_ids = {
        str(p.id) for p in projects if not p.is_hidden and p.repo_link_status != "rejected"
    }
    pending_links = [
        s for s in await suggest_repo_links(db, uid)
        if s.get("confidence") == "fuzzy" and s["project_id"] in visible_project_ids
    ]

    return {
        "experiences": [_experience_item(e) for e in experiences],
        "projects": [_project_item(p) for p in projects],
        "education": [_education_item(e) for e in education],
        "skills": skills,
        "pending_repo_links": pending_links,
        "evidence_updated_at": (
            current_user.evidence_updated_at.isoformat() if current_user.evidence_updated_at else None
        ),
    }


class ReviewRequest(BaseModel):
    action: Literal["confirm", "edit", "hide", "unhide"]
    fields: dict | None = None


@router.patch("/{kind}/{item_id}")
async def review_item(
    kind: str,
    item_id: str,
    payload: ReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm, edit, hide or restore one project, experience or education
    entry. Reviewed items are never overwritten by later syncs or uploads.
    """
    if kind not in KINDS:
        raise HTTPException(status_code=404, detail=f"Unknown kind '{kind}'.")
    try:
        parsed_id = UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Item not found.")

    try:
        row = await apply_review(db, current_user.id, kind, parsed_id, payload.action, payload.fields)
    except ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found.")
    return _SERIALIZERS[kind](row)


class SkillVisibilityRequest(BaseModel):
    hidden: bool


@router.put("/skills/{canonical}/visibility")
async def set_skill_visibility(
    canonical: str,
    payload: SkillVisibilityRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hides or restores a skill for the current user only. Hidden skills
    are left out of every confidence reading (identity, skill gap, planner).
    """
    if not await set_skill_hidden(db, current_user.id, canonical, payload.hidden):
        raise HTTPException(status_code=404, detail="Skill not found.")
    return {"skill": canonical, "is_hidden": payload.hidden}
