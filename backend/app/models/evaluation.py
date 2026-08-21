import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import uuid_pk


class AgentFeedback(Base):
    """Phase 3 placeholder — agent output evaluation / RLHF data collection.

    This table is intentionally unused in Phase 1 and Phase 2. It will be
    populated when LLM outputs are surfaced to users with explicit
    accept/reject controls (design doc §7 — Evaluation & Feedback). The
    `agent_name` column will reference the specific LLM module (e.g.
    'career_planner', 'identity_synthesizer') so that per-module accuracy
    metrics can be computed.

    Do NOT add queries against this table until the Phase 3 feedback
    collection service is implemented; the table will be empty for all
    existing users.
    """
    __tablename__ = "agent_feedback"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String(100))
    input_ref: Mapped[str | None] = mapped_column(String(500))
    output_ref: Mapped[str | None] = mapped_column(String(500))
    accepted: Mapped[bool | None] = mapped_column(Boolean)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))