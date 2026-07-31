import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import uuid_pk


class LeetcodeEngineeringSnapshot(Base):
    """Derived, append-only rollup of the cross-module LeetCode x GitHub
    inference (Engineering Maturity Quadrant, company readiness, resume-
    claim verification) — see LeetCode Module Review §5. One row per
    sync event that could plausibly move the quadrant (a LeetCode sync,
    a manual LeetCode submission, or a GitHub sync), so the quadrant has
    real historical trend instead of only ever reflecting "right now".
    Tied to the LeetCode ProfileSnapshot it was computed alongside for
    lineage; never a source of truth on its own — always safe to
    recompute and re-append from the underlying facts (§5.5 'inference').
    """
    __tablename__ = "leetcode_engineering_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    leetcode_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profile_snapshots.id")
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_event: Mapped[str] = mapped_column(String(50))  # "leetcode sync" | "leetcode manual submission" | "github sync"

    leetcode_score: Mapped[float] = mapped_column(Float)
    github_score: Mapped[float] = mapped_column(Float)
    quadrant_label: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)

    company_readiness: Mapped[list] = mapped_column(JSONB)
    resume_claims: Mapped[dict] = mapped_column(JSONB)