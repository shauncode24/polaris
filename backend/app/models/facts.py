# backend/app/models/facts.py
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, Boolean, Index, false as sa_false, text, true as sa_true
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base_types import created_at_col, uuid_pk


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    auth_provider: Mapped[str] = mapped_column(String(20), default="local")
    target_roles: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    target_companies: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    location_pref: Mapped[str | None] = mapped_column(String(255))
    # Contact details the user typed for their resume.
    phone: Mapped[str | None] = mapped_column(String(40))
    linkedin_url: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = created_at_col()
    github_username: Mapped[str | None] = mapped_column(String(255))
    github_token: Mapped[str | None] = mapped_column(String(512))
    leetcode_username: Mapped[str | None] = mapped_column(String(255))
    # Bumped whenever the user's evidence changes (upload, sync, edit, link).
    # Cached AI reports older than this are out of date.
    evidence_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Experience(Base):
    __tablename__ = "experiences"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"))
    role: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    # As written ("2023", "Present"); see services/resume/dates.py.
    start_date_text: Mapped[str | None] = mapped_column(String(50))
    end_date_text: Mapped[str | None] = mapped_column(String(50))
    stack: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    bullets: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    competency_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    # Phase 4 (provenance) — which ingestion source produced this row.
    # "resume" | "linkedin". Defaults to "resume" so every pre-Phase-4
    # row (all of which came from resume ingestion) reads correctly
    # without a data backfill. REQUIRES a new Alembic migration to add
    # this column to the real database — not generated in this pass.
    source: Mapped[str] = mapped_column(String(20), default="resume")
    # User review of this row. "auto" = produced by extraction/sync and still
    # overwritable; "confirmed" or "edited" = the user has taken ownership, so
    # re-uploads and syncs must not overwrite it. Hidden rows stay stored but
    # are excluded from everything that reads the evidence record.
    review_state: Mapped[str] = mapped_column(String(20), default="auto", server_default="auto")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    # What this row IS, fixed when it was first created and never changed by
    # edits (normalised role@company, project name, ...). Lets a re-upload find
    # the earlier row the user reviewed even after they renamed it. Null on
    # rows from before this existed; readers fall back to the current name.
    dedupe_key: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = created_at_col()


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        # A GitHub-sourced project is one row per repo. Resume-sourced rows
        # are append-only per upload, so the rule only covers source='github'.
        Index(
            "uq_project_user_github_repo", "user_id", "github_repo_name",
            unique=True, postgresql_where=text("source = 'github'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    tagline: Mapped[str | None] = mapped_column(String(255))
    stack: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    repo_url: Mapped[str | None] = mapped_column(String(500))
    github_repo_name: Mapped[str | None] = mapped_column(String(255))
    repo_link_status: Mapped[str] = mapped_column(String(30), default="unmatched")
    impact_metrics: Mapped[dict | None] = mapped_column(JSONB)
    competency_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    # Phase 4 (provenance) — same rule as Experience.source above.
    source: Mapped[str] = mapped_column(String(20), default="resume")
    # User review of this row. "auto" = produced by extraction/sync and still
    # overwritable; "confirmed" or "edited" = the user has taken ownership, so
    # re-uploads and syncs must not overwrite it. Hidden rows stay stored but
    # are excluded from everything that reads the evidence record.
    review_state: Mapped[str] = mapped_column(String(20), default="auto", server_default="auto")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    # What this row IS, fixed when it was first created and never changed by
    # edits (normalised role@company, project name, ...). Lets a re-upload find
    # the earlier row the user reviewed even after they renamed it. Null on
    # rows from before this existed; readers fall back to the current name.
    dedupe_key: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Education(Base):
    __tablename__ = "educations"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"))
    institution: Mapped[str] = mapped_column(String(255))
    degree: Mapped[str | None] = mapped_column(String(255))
    field_of_study: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    # As written ("2023", "Present"); see services/resume/dates.py.
    start_date_text: Mapped[str | None] = mapped_column(String(50))
    end_date_text: Mapped[str | None] = mapped_column(String(50))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    # Phase 4 (provenance) — same rule as Experience.source above.
    source: Mapped[str] = mapped_column(String(20), default="resume")
    # User review of this row. "auto" = produced by extraction/sync and still
    # overwritable; "confirmed" or "edited" = the user has taken ownership, so
    # re-uploads and syncs must not overwrite it. Hidden rows stay stored but
    # are excluded from everything that reads the evidence record.
    review_state: Mapped[str] = mapped_column(String(20), default="auto", server_default="auto")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    # What this row IS, fixed when it was first created and never changed by
    # edits (normalised role@company, project name, ...). Lets a re-upload find
    # the earlier row the user reviewed even after they renamed it. Null on
    # rows from before this existed; readers fall back to the current name.
    dedupe_key: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = created_at_col()


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    issuer: Mapped[str | None] = mapped_column(String(255))
    date: Mapped[date | None] = mapped_column(Date)
    skills: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    created_at: Mapped[datetime] = created_at_col()


class GithubSnapshot(Base):
    __tablename__ = "github_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    pulled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    repo_name: Mapped[str] = mapped_column(String(255))
    commits_30d: Mapped[int | None] = mapped_column(Integer)
    languages: Mapped[dict | None] = mapped_column(JSONB)
    stars: Mapped[int | None] = mapped_column(Integer)


class LeetcodeSnapshot(Base):
    __tablename__ = "leetcode_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    pulled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tag: Mapped[str] = mapped_column(String(100))
    solved_count: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[str | None] = mapped_column(String(20))


class CompanyNote(Base):
    __tablename__ = "company_notes"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    company: Mapped[str] = mapped_column(String(255))
    pasted_content: Mapped[str] = mapped_column(Text)
    extracted_signals: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_col()


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    raw_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = created_at_col()


class UserSkillOverride(Base):
    """A user's decision about one skill in their evidence record. Hiding a
    skill removes it from the confidence map every other feature reads.
    """
    __tablename__ = "user_skill_overrides"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id"), primary_key=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sa_true())
    updated_at: Mapped[datetime] = created_at_col()
