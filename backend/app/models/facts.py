import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, Boolean
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
    created_at: Mapped[datetime] = created_at_col()
    github_username: Mapped[str | None] = mapped_column(String(255))
    github_token: Mapped[str | None] = mapped_column(String(255))
    leetcode_username: Mapped[str | None] = mapped_column(String(255))


class Experience(Base):
    __tablename__ = "experiences"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"))
    role: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    stack: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    bullets: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = created_at_col()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    stack: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    repo_url: Mapped[str | None] = mapped_column(String(500))
    impact_metrics: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_col()


class Education(Base):
    """Facts table (§5.5) — raw, append-only, sourced directly from resume
    extraction. Was missing entirely from the original schema/pipeline,
    which is why education never appeared anywhere downstream (Interview
    Response Agent, Resume Reviewer, etc.) — it was simply never captured,
    not filtered out.
    """
    __tablename__ = "educations"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"))
    institution: Mapped[str] = mapped_column(String(255))
    degree: Mapped[str | None] = mapped_column(String(255))
    field_of_study: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
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


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    company: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    extracted_requirements: Mapped[dict | None] = mapped_column(JSONB)
    analysis_result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_col()


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
    """Raw, immutable resume text — a fact table per §5.5, kept for its
    own sake (ATS-style checks need real layout/wording, not just what
    the extraction pipeline pulled structurally out of it in Phase 2).
    Append-only: every re-upload creates a new row rather than
    overwriting the previous one.
    """
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    raw_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = created_at_col()