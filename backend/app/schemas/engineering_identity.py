from datetime import datetime

from pydantic import BaseModel, field_validator


class IdentityFacts(BaseModel):
    top_skills: list[dict] = []
    role_fit: list[dict] = []
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