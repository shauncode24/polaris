# backend/app/models/github_analysis.py
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import uuid_pk


class GithubProjectAnalysis(Base):
    """Derived, per-repo insight — recomputed and UPSERTED on every sync.
    Unlike github_snapshots (raw, append-only fact), this table is a cache:
    safe to blow away and rebuild if the scoring logic changes (§5.5).
    """
    __tablename__ = "github_project_analysis"
    __table_args__ = (UniqueConstraint("user_id", "repo_name", name="uq_repo_analysis_user_repo"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    repo_name: Mapped[str] = mapped_column(String(255))

    category: Mapped[str] = mapped_column(String(50))                    # "Full Stack" | "Backend" | "Frontend" | "Library/Other"
    primary_language: Mapped[str | None] = mapped_column(String(50))
    technologies: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    capabilities: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    is_backend: Mapped[bool] = mapped_column(Boolean, default=False)
    is_frontend: Mapped[bool] = mapped_column(Boolean, default=False)
    is_database: Mapped[bool] = mapped_column(Boolean, default=False)
    is_containerized: Mapped[bool] = mapped_column(Boolean, default=False)
    has_readme: Mapped[bool] = mapped_column(Boolean, default=False)
    has_tests: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ci: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    last_activity_days: Mapped[int | None] = mapped_column(Integer)
    activity_score: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    maintenance_score: Mapped[float] = mapped_column(Float, default=0.0)
    tier: Mapped[str] = mapped_column(String(50), server_default="experiment")

    # --- Fork / hygiene / collaboration / architecture signals ---
    is_fork: Mapped[bool] = mapped_column(Boolean, default=False)
    is_meaningful_fork_contribution: Mapped[bool] = mapped_column(Boolean, default=False)
    commit_hygiene_score: Mapped[float] = mapped_column(Float, default=0.0)
    collaboration_mode: Mapped[str] = mapped_column(String(20), server_default="solo")
    collaboration_score: Mapped[float] = mapped_column(Float, default=0.0)
    architecture_assessment: Mapped[dict | None] = mapped_column(JSONB)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GithubRepoAnalysisCache(Base):
    """SHA-gated cache of the SLOW per-repo computations only: commit
    hygiene sampling, PR/review lookups (~16 requests per repo with
    PRs), fork-contribution commit counting, and the architecture-depth
    LLM pass (tree fetch + model call). Keyed by the repo's last commit
    SHA rather than a TTL — if HEAD hasn't moved since the last sync,
    none of these signals could have changed, so reuse is always safe,
    never stale. Cheap per-repo checks (languages, README/CI/tests
    existence, manifest scans) are NOT cached here and are still
    refetched every sync — they're single lightweight calls where
    caching would save little and risks staleness if a file changes
    without a new commit being what triggers the sync (e.g. force-push).
    Separate from GithubProjectAnalysis, which is the full rendered
    per-sync analysis and always gets rewritten regardless of cache hits.
    """
    __tablename__ = "github_repo_analysis_cache"
    __table_args__ = (UniqueConstraint("user_id", "repo_name", name="uq_repo_cache_user_repo"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    repo_name: Mapped[str] = mapped_column(String(255))
    last_commit_sha: Mapped[str] = mapped_column(String(64))

    commit_hygiene: Mapped[dict] = mapped_column(JSONB)
    pr_stats: Mapped[dict] = mapped_column(JSONB)
    collaboration: Mapped[dict] = mapped_column(JSONB)
    fork_contribution_commits: Mapped[int] = mapped_column(Integer, default=0)
    architecture_assessment: Mapped[dict | None] = mapped_column(JSONB)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PortfolioAnalysis(Base):
    """Derived, portfolio-wide rollup — ONE ROW PER SYNC (append-only),
    because trend observations ("Docker usage increased") require the
    previous row to diff against. Tied to the profile_snapshots row
    written by that same sync.
    """
    __tablename__ = "portfolio_analysis"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profile_snapshots.id"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    active_projects: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    neglected_projects: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    strongest_projects: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    recently_active_projects: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    technology_distribution: Mapped[dict] = mapped_column(JSONB)   # {"FastAPI": 4, "React": 7, ...}
    quality_metrics: Mapped[dict] = mapped_column(JSONB)           # {"repos_with_tests": 3, "repos_without_readme": 9, ...}
    observations: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)