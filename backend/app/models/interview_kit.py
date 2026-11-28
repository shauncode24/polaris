import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import created_at_col, uuid_pk


class InterviewKit(Base):
    """One version of the interview kit for one job. A new kit is a new version,
    so practice recorded against an earlier one's questions is kept.
    """
    __tablename__ = "interview_kits"
    __table_args__ = (
        UniqueConstraint("user_id", "job_intelligence_id", "version", name="uq_interview_kit_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    job_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_intelligence_profiles.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)  # 1, 2, ... for each job
    seniority: Mapped[str] = mapped_column(String(20))  # the job's, when the kit was made
    notice: Mapped[str | None] = mapped_column(Text)
    # When the record was read to match the questions' evidence. Older than the
    # user's `evidence_updated_at` means the matching is out of date.
    evidence_mapped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_notice: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()


class InterviewQuestion(Base):
    """One question of a kit (`KitQuestion` in schemas/interview/kit.py). It
    belongs to whoever owns the kit, so look it up through the kit.
    """
    __tablename__ = "interview_questions"
    __table_args__ = (UniqueConstraint("kit_id", "position", name="uq_interview_question_position"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    kit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_kits.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)  # 0, 1, ... in the kit's order
    category: Mapped[str] = mapped_column(String(20))
    topic: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    skills: Mapped[list] = mapped_column(JSONB)
    competencies: Mapped[list] = mapped_column(JSONB)
    origin: Mapped[str] = mapped_column(String(10))
    # The candidate's evidence for answering it (`QuestionEvidence`), and whether
    # none qualified. Empty and NULL until matched against the record.
    evidence_refs: Mapped[list] = mapped_column(JSONB, default=list)
    thin_evidence: Mapped[bool | None] = mapped_column(Boolean)
