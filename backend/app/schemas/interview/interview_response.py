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


class GroundingReport(BaseModel):
    """Deterministic, non-LLM check — never rewrites the answer, only
    reports. See services/interview/grounding.py. This SAME shape is
    reused for two distinct passes now (Phase 1):
      - validate_plan(): runs on the structured AnswerPlan, BEFORE any
        prose exists — this is what actually gates a re-plan attempt.
      - validate_answer(): runs on the final prose, AFTER generation —
        a last-line defensive scan, purely advisory (nothing blocks on
        this one, since by this point the plan already passed).
    """
    unverifiable_claims: list[str] = []
    uses_flagged_project: bool = False
    possible_fabricated_entities: list[str] = []


class PlanEvidenceCitation(BaseModel):
    """One piece of evidence the plan is relying on — `source` MUST be
    a real, literal name from the candidate's profile (a project name,
    a "{role} at {company}" experience label, or a github_repos entry's
    name); `fact` is the specific detail drawn from that source. This
    is the mechanism that makes pre-prose grounding possible at all:
    without a structured citation, there'd be nothing to check a claim
    against except free text.
    """
    source: str
    fact: str


class PlanSection(BaseModel):
    """One blueprint section, filled with factual notes — NOT yet
    styled prose. Kept terse and declarative on purpose; all of the
    persona/voice work (contractions, plain-language-before-jargon,
    bridge sentences, sentence-length variation) happens later, in the
    prose-generation stage, over content that has already been
    validated against the real profile.
    """
    label: str
    content: str


class AnswerPlan(BaseModel):
    """The Phase 1 intermediate stage (implementation plan §F/§G). The
    model reasons over the ENTIRE real profile here, once, and commits
    to a set of real, citable facts. Everything downstream (prose
    generation) is only ever allowed to restyle THIS object — it can
    no longer introduce a new fact, story, or number, which is what
    makes pre-prose grounding meaningful: reject/re-plan here is cheap
    and catches a hallucination before it's dressed up in natural
    language and harder to spot.
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
    facts, so it never needs its own grounding pass against the profile
    (the plan already cleared that bar); the post-prose scan in
    grounding.validate_answer() is a defensive-in-depth safety net only.
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
    context_note: str = ""
    claims_needing_verification: list[str] = []
    grounding: GroundingReport = GroundingReport()


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