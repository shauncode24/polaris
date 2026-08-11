# backend/app/api/company_notes.py
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import CompanyNote, User
from app.schemas.shared.company_notes import CompanyNoteCreateRequest, CompanyNoteResponse

router = APIRouter(prefix="/company-notes", tags=["company-notes"])


@router.post("", response_model=CompanyNoteResponse)
async def create_company_note(
    payload: CompanyNoteCreateRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    note = CompanyNote(
        user_id=current_user.id,
        company=payload.company,
        pasted_content=payload.pasted_content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return CompanyNoteResponse(
        id=str(note.id), company=note.company, pasted_content=note.pasted_content, created_at=note.created_at,
    )


@router.get("", response_model=list[CompanyNoteResponse])
async def list_company_notes(
    company: str | None = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    stmt = select(CompanyNote).where(CompanyNote.user_id == current_user.id)
    if company:
        stmt = stmt.where(CompanyNote.company.ilike(company))
    stmt = stmt.order_by(CompanyNote.created_at.desc())
    result = await db.execute(stmt)
    return [
        CompanyNoteResponse(id=str(n.id), company=n.company, pasted_content=n.pasted_content, created_at=n.created_at)
        for n in result.scalars().all()
    ]