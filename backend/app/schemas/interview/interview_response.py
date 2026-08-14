# backend/app/schemas/interview/interview_response.py
from datetime import datetime

from pydantic import BaseModel


class InterviewAskRequest(BaseModel):
    question: str
    target_role: str | None = None
    target_company: str | None = None
    job_intelligence_id: str | None = None
    session_id: str | None = None
    parent_response_id: str | None = None
    correction: str | None = None


class CoachingNote(BaseModel):
    focus: str
    note: str


class BlueprintClassification(BaseModel):
    blueprint_key: str
    reason: str = ""
    # NEW (implementation plan §A) — a confidence read on the match
    # itself, and the competency tags the classifier believes this
    # question tests, independent of whatever competency hints the
    # matched blueprint happens to carry in BLUEPRINT_COMPETENCY_HINTS.
    # Never trusted blindly downstream — competency_tags is filtered to
    # the same CANONICAL_COMPETENCIES vocabulary used everywhere else
    # in the interview module (see competency_tagging.py) before use.
    confidence: str = "medium"  # "low" | "medium" | "high"
    competency_tags: list[str] = []


class GroundingReport(BaseModel):
    """Deterministic, non-LLM check — never rewrites the answer, only
    reports. See services/interview/grounding.py. This SAME shape is
    reused for two distinct passes:
      - validate_plan(): runs on the structured AnswerPlan, BEFORE any
        prose exists — this is what actually gates a re-plan attempt.
      - validate_answer(): runs on the final prose, AFTER generation —
        a last-line defensive scan, purely advisory.
    """
    unverifiable_claims: list[str] = []
    uses_flagged_project: bool = False
    possible_fabricated_entities: list[str] = []


class PlanEvidenceCitation(BaseModel):
    """One piece of evidence the plan is relying on — `source` MUST be
    a real, literal name from the candidate's profile (a project name,
    a "{role} at {company}" experience label, or a github_repos entry's
    name); `fact` is the specific detail drawn from that source.
    """
    source: str
    fact: str


class PlanSection(BaseModel):
    """One blueprint section, filled with factual notes — NOT yet
    styled prose. All persona/voice work happens later, in the
    prose-generation stage, over content already validated against the
    real profile.
    """
    label: str
    content: str


class AnswerPlan(BaseModel):
    """The Phase 1 intermediate stage. The model reasons over the
    ENTIRE real profile here, once, and commits to a set of real,
    citable facts. Prose generation is only ever allowed to restyle
    THIS object.
    """
    question_type: str = ""
    blueprint_used: str = ""
    competencies: list[str] = []
    stories_used: list[str] = []
    sections: list[PlanSection] = []
    cited_evidence: list[PlanEvidenceCitation] = []
    follow_up_questions: list[str] = []
    coaching: list[CoachingNote] = []
    insufficient_context: bool = False
    context_note: str = ""
    claims_needing_verification: list[str] = []


class ProseOutput(BaseModel):
    """The narrow, low-risk second-stage output — restyles an already-
    validated AnswerPlan into spoken-style prose. Never carries new
    facts.
    """
    answer: str = ""
    answer_short: str = ""


class InterviewLLMOutput(BaseModel):
    question_type: str
    blueprint_used: str = ""
    competencies: list[str] = []
    stories_used: list[str] = []
    answer: str = ""
    answer_short: str = ""
    follow_up_questions: list[str] = []
    coaching: list[CoachingNote] = []
    insufficient_context: bool = False
    # WHY insufficient_context is true: "empty_profile" |
    # "model_declined" | "grounding_rejected". "" whenever false.
    insufficient_context_reason: str = ""
    context_note: str = ""
    claims_needing_verification: list[str] = []
    grounding: GroundingReport = GroundingReport()
    # Phase 3 §Q/§R — the prompt version hash that generated this
    # output, set by generate_interview_response() using the stable
    # 8-char prefix of the combined plan+prose prompt hashes.
    prompt_version: str = ""


class InterviewResponseOutput(BaseModel):
    response_id: str | None = None
    question: str
    question_type: str
    blueprint_used: str = ""
    answer: str
    answer_short: str = ""
    stories_used: list[str] = []
    competencies: list[str] = []
    follow_up_questions: list[str] = []
    coaching: list[CoachingNote] = []
    insufficient_context: bool = False
    insufficient_context_reason: str = ""
    context_note: str = ""
    target_role: str | None = None
    target_company: str | None = None
    created_at: datetime | None = None
    claims_needing_verification: list[str] = []
    grounding: GroundingReport = GroundingReport()
    session_id: str | None = None
    parent_response_id: str | None = None
    correction_of: str | None = None
    suggested_action: str | None = None
    trace_id: str | None = None
    # NEW (implementation plan §M) — set when job_intelligence_id was
    # not explicitly passed by the caller but a real, active Goal's
    # attached job was auto-attached instead, so the frontend can show
    # "using context from your goal: X" rather than the JD context
    # silently appearing with no explanation.
    auto_attached_job_intelligence_id: str | None = None
    # Phase 3 §Q/§R — prompt version hash for observability + regression
    # tracking. Format: "<8-char plan hash>/<8-char prose hash>" derived
    # deterministically from the actual prompt content, so it updates
    # automatically whenever a prompt changes.
    prompt_version: str | None = None


class InterviewSessionSummary(BaseModel):
    id: str
    question: str
    question_type: str
    target_role: str | None = None
    target_company: str | None = None
    created_at: datetime
    session_id: str | None = None


class CorrectionRequest(BaseModel):
    parent_response_id: str
    correction: str