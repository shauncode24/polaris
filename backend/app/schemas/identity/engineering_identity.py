from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.identity.role_fit import RoleFitResult  # noqa: F401 — re-exported as part of IdentityFacts typing


class TopSkillEntry(BaseModel):
    """One entry in IdentityFacts.top_skills — typed to match exactly what
    confidence_reconciliation.reconcile_skill_confidence() returns: the
    original `confidence` (post-discount), the pre-discount `raw_confidence`,
    a list of `confidence_flags` explaining any discount, and the backing
    `sources` / `corroboration_count` from SkillEvidence.
    """
    skill: str
    confidence: float
    raw_confidence: float = 0.0  # populated by reconcile_skill_confidence; 0.0 = no discount applied
    confidence_flags: list[str] = []
    sources: list[str] = []
    corroboration_count: int = 0


class PortfolioNarrativeFacts(BaseModel):
    """Subset of PortfolioNarrativeReport fields that are surfaced inside
    IdentityFacts so Identity's synthesis can reason over the portfolio-wide
    signal from the Projects module. Intentionally the human-readable
    narrative strings only — the raw counts live on PortfolioNarrativeReport
    and don't need to be duplicated here.
    """
    narrative: str = ""
    testing_pattern: str = ""
    collaboration_pattern: str = ""
    specialization: str = ""
    biggest_weakness: str = ""
    analysis_degraded: bool = False


# ---------------------------------------------------------------------------
# Phase 3 — Polaris Identity: structured professional profile sub-schema
#
# These models capture the user's professional history as it existed at the
# moment an EngineeringIdentity snapshot was generated. They are sourced
# exclusively from the existing domain tables (Experience, Education, Project,
# User, Goal) and deduplicated by the same normalize_name() rule every other
# module already uses — they do NOT duplicate domain ownership, only
# reconcile and snapshot it.
#
# All fields are optional / defaulted so that existing serialised
# facts_json blobs (which lack the "profile" key) deserialise cleanly
# with profile=None — no migration required.
# ---------------------------------------------------------------------------

class ProfileExperienceEntry(BaseModel):
    """Deduplicated resume experience record — one per unique role+company
    combination. Sourced from the Experience table (facts layer).

    Evidence provenance:
      Source table: experiences (facts.py::Experience)
      Deduplication key: normalize_name(role) + "@" + normalize_name(company)
      Source event: resume upload (resume parser → resume_extraction.py)
    """
    role: str
    company: str
    start_date: str | None = None  # ISO date string, e.g. "2022-06-01"
    end_date: str | None = None    # None means current position
    stack: list[str] = []          # Raw stack strings from resume
    bullets: list[str] = []        # Achievement/responsibility bullets


class ProfileEducationEntry(BaseModel):
    """Deduplicated education record. Sourced from the Education table.

    Evidence provenance:
      Source table: educations (facts.py::Education)
      Deduplication key: normalize_name(institution) + "@" + normalize_name(degree)
      Source event: resume upload
    """
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    end_date: str | None = None  # None for current students
    is_current: bool = False


class ProfileProjectEntry(BaseModel):
    """Deduplicated project record with GitHub link status. Sourced from
    the Project table.

    Evidence provenance:
      Source table: projects (facts.py::Project)
      Deduplication key: normalize_name(name)
      Source event: resume upload and/or manual project creation
      GitHub link: repo_link_status tracks whether a GitHub repo has been
        confirmed as backing this project (confirmed > unmatched > rejected)
    """
    name: str
    description: str | None = None
    stack: list[str] = []
    repo_link_status: str = "unmatched"  # "confirmed" | "unmatched" | "rejected"


class PolarisProfileFacts(BaseModel):
    """The canonical structured professional profile — the Phase 3 addition
    to IdentityFacts. Represents the user's professional identity as a
    reconciled, deduplicated snapshot of existing domain facts at the time
    of identity generation.

    This is NOT a copy of the domain tables. It is a cross-domain reconciled
    view that answers "who is this engineer, professionally?" at a glance:

      Domain Data (Experience/Education/Project/User/Goal)
           ↓
      build_profile_facts() — dedup, reconcile, snapshot
           ↓
      PolarisProfileFacts (inside IdentityFacts, persisted in facts_json)
           ↓
      Downstream consumers (Identity API, Career Planner, Interview Agent)

    All fields default so pre-Phase-3 facts_json blobs deserialise cleanly
    with profile=None (no Alembic migration required).
    """
    experiences: list[ProfileExperienceEntry] = []
    education: list[ProfileEducationEntry] = []
    projects: list[ProfileProjectEntry] = []

    # Career direction — from User.target_roles / User.target_companies
    target_roles: list[str] = []
    target_companies: list[str] = []

    # Active goal count — how many in-progress goals exist (not the full
    # Goal objects — those belong to the career domain, not identity)
    active_goal_count: int = 0


class IdentityFacts(BaseModel):
    top_skills: list[TopSkillEntry] = []
    role_fit: list[RoleFitResult] = []
    # Hash of the all_sources scoped skill evidence that produced
    # role_fit. Read back on the next refresh to decide whether the
    # evidence actually changed, or whether the previous role_fit
    # rating can be safely reused instead of paying for (and risking
    # temperature-driven drift from) another LLM call.
    role_fit_evidence_hash: str = ""
    resume_score: float | None = None
    resume_grade: str | None = None
    github_summary: dict = {}
    github_progress: dict = {}
    architecture_maturity: dict = {}
    technology_depth_highlights: list[dict] = []
    technology_breadth: dict = {}
    leetcode_summary: dict = {}
    leetcode_topic_mastery: list[dict] = []
    engineering_quadrant: dict | None = None
    company_readiness: list[dict] = []
    coverage_gaps: dict = {}
    timeline_plausibility_notes: list[dict] = []
    active_goals: list[dict] = []
    recent_job_matches: list[dict] = []
    claim_risk_details: list[dict] = []
    # NEW (audit finding #1) — per-source {"as_of", "age_days",
    # "is_stale", "connected"}, e.g. source_freshness["github"]. Lets a
    # consumer (human or the synthesis LLM itself) see how current each
    # blended-in piece of this object actually is, instead of every
    # source being silently flattened into one implicit "now".
    source_freshness: dict = {}
    # NEW (audit finding #2) — deterministic completeness rollup
    # derived from source_freshness: how many sources are connected,
    # stale, or missing, and a coarse completeness label. Distinguishes
    # "this profile has no GitHub evidence because none exists yet"
    # from "this profile is a considered, complete picture."
    evidence_coverage: dict = {}
    # NEW (Projects completeness fix) — portfolio-wide narrative signals from
    # PortfolioNarrativeReview (testing pattern, collaboration pattern,
    # specialization, biggest weakness). None when no narrative has been
    # generated yet (user hasn't synced enough projects).
    portfolio_narrative: PortfolioNarrativeFacts | None = None
    # Phase 3 — Polaris Identity: canonical structured professional profile.
    # None for existing snapshots that pre-date Phase 3 (no migration needed).
    profile: PolarisProfileFacts | None = None


class NarrativeClaim(BaseModel):
    """A single narrative statement, tagged with whether it's a direct
    citation of a real computed fact or the model's own interpretive
    judgment — audit finding #4. "grounded_in" should point to the
    specific IdentityFacts field/value being cited (e.g.
    "top_skills: docker (confidence 0.81, corroboration_count=2)") when
    kind == "fact"; it's optional prose context when kind ==
    "interpretation" (e.g. "synthesized from technology_breadth +
    engineering_quadrant").
    """
    statement: str
    kind: str = "interpretation"  # "fact" | "interpretation"
    grounded_in: str = ""


class IdentityLLMOutput(BaseModel):
    headline: str = ""
    summary: str = ""
    strongest_signals: list[NarrativeClaim] = []
    biggest_gaps: list[NarrativeClaim] = []
    contradictions: list[str] = []
    recommended_focus: str = ""
    # NEW (audit finding #1) — the model's own plain-language read of
    # source_freshness/evidence_coverage, e.g. "Your GitHub picture is
    # 21 days old, but your resume was updated 2 days ago — treat the
    # GitHub-derived signals below as a slightly dated snapshot."
    freshness_note: str = ""

    @field_validator("strongest_signals", "biggest_gaps", mode="before")
    @classmethod
    def validate_narrative_claims(cls, v):
        if not isinstance(v, list):
            return v
        cleaned = []
        for item in v:
            if isinstance(item, str):
                cleaned.append({"statement": item, "kind": "interpretation", "grounded_in": ""})
            else:
                cleaned.append(item)
        return cleaned


class EngineeringIdentityReport(BaseModel):
    facts: IdentityFacts
    narrative: IdentityLLMOutput
    generated_at: datetime | None = None
    analysis_degraded: bool = False
    # Freshness fix — which real event produced this snapshot: "resume
    # upload", "resume analysis", "github sync", "leetcode sync",
    # "leetcode manual submission", "job description analysis", "claim
    # audit", "project link confirmed", "project link removed", or
    # "manual_refresh" for an explicit POST /identity/refresh call.
    source_event: str = "manual_refresh"
    # NEW (audit finding #3) — lightweight invalidation, not full
    # versioning. A past row is never deleted or rewritten (append-only
    # history stays intact for Weekly Brief's diffing), but it CAN be
    # explicitly flagged as known-bad after the fact (e.g. a GitHub API
    # hiccup fed a wrong scoring input into this snapshot's facts).
    is_invalidated: bool = False
    invalidated_reason: str | None = None
    invalidated_at: datetime | None = None


class InvalidateIdentityRequest(BaseModel):
    reason: str