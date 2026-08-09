# backend/app/models/job_intelligence.py
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import uuid_pk


class JobIntelligenceProfileRow(Base):
    """Persisted Job Intelligence — a user-independent representation of
    what a role requires (design doc §2.6). Keyed conceptually by
    (user_id who submitted it, source_text_hash) — not globally
    deduplicated across users yet, a deliberate scope decision so a
    future global-cache optimization is additive, not a breaking
    migration.
    """
    __tablename__ = "job_intelligence_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    source_text_hash: Mapped[str] = mapped_column(String(64), index=True)
    profile_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CompanyIntelligenceProfileRow(Base):
    """Persisted Company Intelligence — extracted from the SAME job
    description text as its sibling JobIntelligenceProfileRow (one LLM
    call, two profiles). Deliberately no FK to JobIntelligenceProfileRow
    at the schema level so either can evolve independently; the two are
    related only via source_text_hash and by both being produced in the
    same build_job_intelligence() call.
    """
    __tablename__ = "company_intelligence_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    source_text_hash: Mapped[str] = mapped_column(String(64), index=True)
    profile_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GapAnalysisResultRow(Base):
    """Replaces JobDescription.analysis_result's fused JSONB blob for
    lineage purposes (design doc §5, Phase 3). References both source
    profiles by id — same append-only, source-tagged pattern as
    LeetcodeEngineeringSnapshot.source_event / EngineeringIdentity.source_event.
    JobDescription.analysis_result is still ALSO written for now
    (dual-write, Phase 2/3) so GET /jobs/{id} keeps working unchanged.
    """
    __tablename__ = "gap_analysis_results"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    job_intelligence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_intelligence_profiles.id"), index=True
    )
    company_intelligence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company_intelligence_profiles.id")
    )
    report_json: Mapped[dict] = mapped_column(JSONB)
    category_breakdown_json: Mapped[dict] = mapped_column(JSONB)
    overall_match_json: Mapped[dict] = mapped_column(JSONB)
    narrative_json: Mapped[dict] = mapped_column(JSONB)
    analysis_degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))