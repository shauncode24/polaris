import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import uuid_pk


class SkillEvidence(Base):
    __tablename__ = "skill_evidence"

    id: Mapped[uuid.UUID] = uuid_pk()
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(50))  # "project" | "experience" | "certificate" | "leetcode_tag"
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    weight: Mapped[float] = mapped_column(Float)


class ProfileSnapshot(Base):
    __tablename__ = "profile_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    skills_json: Mapped[dict] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(Text)


class ReadinessScore(Base):
    __tablename__ = "readiness_scores"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    goal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    score: Mapped[float] = mapped_column(Float)
    basis: Mapped[str | None] = mapped_column(Text)