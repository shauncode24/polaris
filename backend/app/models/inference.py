import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import uuid_pk


class SkillEvidence(Base):
    __tablename__ = "skill_evidence"

    id: Mapped[uuid.UUID] = uuid_pk()
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(50))
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


class ResumeReview(Base):
    """Derived, recomputable review output (§5.5 'inference') — never a
    source of truth, safe to regenerate any time bullet_analysis.py or
    the LLM prompt changes. Tied to the specific Resume row it reviewed
    so you can see review quality evolve as the resume itself evolves.
    """
    __tablename__ = "resume_reviews"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"))
    review_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

class CareerPlan(Base):
    """Derived, recomputable roadmap output (§5.5 'inference') — one row
    per plan generation, tied to the Goal it was generated for. The Goal
    and the skill evidence behind it are the source of truth; this table
    is a cache of one particular LLM reasoning pass over that truth, safe
    to regenerate any time the prompt or context-building logic changes.
    """
    __tablename__ = "career_plans"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    goal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id"), index=True)
    plan_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

class InterviewResponse(Base):
    """Derived, recomputable output (§5.5 'inference') — one row per
    question asked, so the design doc's own test case ('ask it 4-5
    questions in a row') has a real history to inspect afterward. Never
    a source of truth: safe to regenerate any time the prompt or
    story-ranking logic changes.
    """
    __tablename__ = "interview_responses"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(100))
    response_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ResumeAnalysis(Base):
    """Deterministic analysis engine output (§5.5 'inference').

    One row per engine run, tied to the specific Resume it analyzed.
    Pure derived data — safe to regenerate any time an analysis module
    changes. Separate from ResumeReview (LLM narrative + rewrites) so
    the two pipelines can evolve independently.
    """
    __tablename__ = "resume_analyses"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"))
    analysis_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class GithubPortfolioReview(Base):
    """LLM career-interpretation layer over the deterministic GitHub
    analysis (github_analyzer.py / github_insights.py / GithubProjectAnalysis).
    One row per review run — this table never computes a single fact
    itself (no scores, no technology detection); it only stores the
    model's read of facts that are already verified elsewhere. Safe to
    regenerate any time the prompt or github_knowledge.py's shape changes.
    """
    __tablename__ = "github_portfolio_reviews"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    review_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class LeetcodePortfolioReview(Base):
    """LLM career-interpretation layer over the deterministic LeetCode
    analysis (leetcode_sync.py / leetcode_insights.py).
    One row per review run — stores the model's read of LeetCode facts,
    including comparisons to GitHub-derived practical engineering capabilities.
    Safe to regenerate any time the prompt or leetcode_knowledge.py's shape changes.
    """
    __tablename__ = "leetcode_portfolio_reviews"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    review_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

class ResumeCoherenceReview(Base):
    """Derived, recomputable narrative-coherence output (§5.5 'inference').
    One row per (resume, target_role) — UPSERTED, not appended, since a
    coherence read for a given resume + role is always safe to
    regenerate and there's no value in accumulating stale duplicates.
    This is what lets the Resume page load an existing report instantly
    instead of re-running the LLM call every visit.
    """
    __tablename__ = "resume_coherence_reviews"
    __table_args__ = (UniqueConstraint("resume_id", "target_role", name="uq_coherence_resume_role"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    resume_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"), index=True)
    target_role: Mapped[str] = mapped_column(String(255), default="")
    report_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ResumeTailoringReview(Base):
    """Derived, recomputable tailoring output (§5.5 'inference'). One row
    per (resume, job_description) pair — UPSERTED so re-running tailoring
    against the same JD replaces the stale recommendation instead of
    accumulating duplicates.
    """
    __tablename__ = "resume_tailoring_reviews"
    __table_args__ = (
        UniqueConstraint("resume_id", "job_description_id", name="uq_tailoring_resume_jd"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    resume_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"), index=True)
    job_description_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id"), index=True
    )
    report_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ProjectClaimAuditReview(Base):
    """Derived, recomputable claim-vs-implementation audit (§5.5
    'inference'). UPSERTED, one row per project — a claim audit for a
    given project is always safe to regenerate (the resume text and
    GitHub-verified facts it diffs are the real source of truth), and
    there's no value in keeping stale duplicates around. Lets the
    Projects page load an existing audit instantly instead of re-running
    the LLM call every visit.
    """
    __tablename__ = "project_claim_audit_reviews"
    __table_args__ = (UniqueConstraint("project_id", name="uq_claim_audit_project"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True)
    report_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ProjectIntelligenceReview(Base):
    """Derived, recomputable Project Intelligence output (§5.5
    'inference'). UPSERTED by (project_id, framing, comparison_target) —
    the same framing asked twice should return the same cached read
    instead of spending another LLM call, but a different framing (or a
    different comparison target) is a genuinely different question and
    gets its own cached row.
    """
    __tablename__ = "project_intelligence_reviews"
    __table_args__ = (
        UniqueConstraint("project_id", "framing", "comparison_target", name="uq_intelligence_project_framing"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True)
    framing: Mapped[str] = mapped_column(String(500), default="")
    comparison_target: Mapped[str] = mapped_column(String(255), default="")
    report_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ProjectInterviewQuestionsReview(Base):
    """Derived, recomputable per-project interview-question set (§5.5
    'inference'). UPSERTED, one row per project.
    """
    __tablename__ = "project_interview_questions_reviews"
    __table_args__ = (UniqueConstraint("project_id", name="uq_interview_questions_project"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True)
    report_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PortfolioNarrativeReview(Base):
    """LLM portfolio-wide engineering-maturity narrative (§5.5
    'inference'). APPEND-ONLY, same pattern as GithubPortfolioReview —
    one row per generation, read back as "latest" by default so a
    returning user sees history accumulate rather than a single
    overwritten row.
    """
    __tablename__ = "portfolio_narrative_reviews"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    report_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )