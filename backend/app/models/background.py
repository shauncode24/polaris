import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import created_at_col, uuid_pk

JOB_RUNNING = "running"
JOB_SUCCEEDED = "succeeded"
JOB_FAILED = "failed"


class BackgroundJob(Base):
    """One piece of slow work a request started and the page is waiting for.

    Not to be confused with a job posting (`job_intelligence_profiles`).
    """
    __tablename__ = "background_jobs"
    __table_args__ = (
        # The same work can't run twice at once for one user.
        Index(
            "uq_background_jobs_running", "user_id", "dedupe_key",
            unique=True, postgresql_where=text("status = 'running'"),
        ),
        Index("ix_background_jobs_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(60))
    dedupe_key: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    result_json: Mapped[dict | list | None] = mapped_column(JSONB(none_as_null=True))
    error_status: Mapped[int | None] = mapped_column(Integer)
    error_json: Mapped[dict | list | str | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = created_at_col()
    # Touched while the work runs; a running job that stops being touched
    # died with its server.
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
