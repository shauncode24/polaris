# backend/app/schemas/company_notes.py
from datetime import datetime

from pydantic import BaseModel


class CompanyNoteCreateRequest(BaseModel):
    company: str
    pasted_content: str


class CompanyNoteResponse(BaseModel):
    id: str
    company: str
    pasted_content: str
    created_at: datetime