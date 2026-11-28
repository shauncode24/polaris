import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import created_at_col, uuid_pk

RESUME_DRAFT = "draft"
RESUME_FINAL = "final"


class TailoredResume(Base):
    """One version of the resume tailored to one job. `content_json` is a
    `TailoredResumeDocument` (schemas/resume/tailored.py).
    """
    __tablename__ = "tailored_resumes"
    __table_args__ = (
        UniqueConstraint("user_id", "job_intelligence_id", "version", name="uq_tailored_resume_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    job_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_intelligence_profiles.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)  # 1, 2, ... for each job
    status: Mapped[str] = mapped_column(String(20), default=RESUME_DRAFT)
    content_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_col()
