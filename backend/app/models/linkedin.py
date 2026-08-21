import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import uuid_pk


class LinkedInProfile(Base):
    """Raw + parsed LinkedIn profile data — a facts table (§5.5 pattern),
    append-only like Resume: every re-paste creates a new row rather than
    overwriting the previous one.

    LinkedIn is ingested via user-pasted profile text ONLY (headline,
    about, experience, education, skills, achievements) — never
    scraped. `raw_text` is the exact pasted content; `parsed_json` is
    the LLM-extracted structured shape (see schemas/linkedin/linkedin.py),
    kept verbatim for provenance/debugging even though the RECONCILED
    facts (written into Experience/Education/SkillEvidence by
    services/linkedin/linkedin_ingestion.py) are what actually feed
    Polaris Identity.
    """
    __tablename__ = "linkedin_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    parsed_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))