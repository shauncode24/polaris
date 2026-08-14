# backend/app/models/structure.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import uuid_pk


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255))
    canonical_name: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    category: Mapped[str | None] = mapped_column(String(100))


class Capability(Base):
    __tablename__ = "capabilities"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), unique=True)
    category: Mapped[str | None] = mapped_column(String(100))


class ProjectSkill(Base):
    __tablename__ = "project_skills"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id"), primary_key=True
    )


class ProjectCapability(Base):
    __tablename__ = "project_capabilities"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True
    )
    capability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("capabilities.id"), primary_key=True
    )


class CapabilityRequirement(Base):
    __tablename__ = "capability_requirements"

    job_description_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id"), primary_key=True
    )
    capability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("capabilities.id"), primary_key=True
    )
    importance: Mapped[float | None] = mapped_column(Float)


class SkillAlias(Base):
    """A cache of raw-string -> canonical-skill classification decisions.

    Tier 1 of skill resolution (the hardcoded dict in skill_classifier.py)
    handles common, well-known spellings for free. Tier 2 is this table —
    once an LLM has classified an unfamiliar raw string (e.g. "Modular
    components" -> not a real skill, or "K8s" -> "kubernetes"), that
    decision is persisted here so it never needs to be re-classified by
    an LLM again, across any user's resume, from this point forward.
    """

    __tablename__ = "skill_aliases"

    id: Mapped[uuid.UUID] = uuid_pk()
    raw_string: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    canonical_name: Mapped[str | None] = mapped_column(String(255))
    is_valid_skill: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class CompetencyTagAlias(Base):
    """Cache of text-hash -> LLM-classified interview-competency tags —
    tier 2 of competency tagging (services/interview/competency_tagging.py).
    Once a piece of evidence text (a project description, an experience's
    bullets) has been classified, that decision is persisted here so it's
    never re-classified again, for any user, from this point forward —
    same pattern as SkillAlias above. Keyed by a hash of the text itself
    rather than a project/experience id, since the same bullet text can
    legitimately recur across different rows (re-uploads, near-duplicate
    experiences) and shouldn't cost a second LLM call each time.
    """

    __tablename__ = "competency_tag_cache"

    id: Mapped[uuid.UUID] = uuid_pk()
    text_hash: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )