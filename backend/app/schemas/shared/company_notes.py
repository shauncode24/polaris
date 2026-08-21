# backend/app/schemas/company_notes.py
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.settings import settings


class CompanyNoteCreateRequest(BaseModel):
    company: str
    pasted_content: str

    @field_validator("company")
    @classmethod
    def validate_company(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("company must not be empty.")
        if len(stripped) > 255:
            raise ValueError("company must be 255 characters or fewer.")
        return v

    @field_validator("pasted_content")
    @classmethod
    def validate_pasted_content(cls, v: str) -> str:
        # SECURITY FIX (Phase 1 §1.4 — input-size limits).
        stripped = v.strip()
        if not stripped:
            raise ValueError("pasted_content must not be empty.")
        if len(stripped) > settings.max_paste_text_chars:
            raise ValueError(
                f"pasted_content exceeds the maximum allowed length of {settings.max_paste_text_chars} characters."
            )
        return v


class CompanyNoteResponse(BaseModel):
    id: str
    company: str
    pasted_content: str
    created_at: datetime