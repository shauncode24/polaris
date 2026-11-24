import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import created_at_col, uuid_pk


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    job_intelligence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_intelligence_profiles.id")
    )
    title: Mapped[str] = mapped_column(String(500))
    deadline: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[str | None] = mapped_column(String(50))
    status_pct: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = created_at_col()
