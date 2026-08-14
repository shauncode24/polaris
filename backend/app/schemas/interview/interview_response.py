# backend/app/schemas/interview_response.py
from datetime import datetime

from pydantic import BaseModel


class InterviewAskRequest(BaseModel):
    question: str
    target_role: str | None = None
    target_company: str | None = None
    job_intelligence_id: str | None = None
    # Session threading — if session_id is omitted, the API layer
    # generates one and returns it, so the frontend can thread every
    # subsequent call in the same conversation.
    session_id: str | None = None
    parent_response_id: str | None = None
    # Set only by POST /interview/correct's internal re-ask; accepted
    # here too so the same request/response plumbing serves both.
    correction: str | None = None


class CoachingNote(BaseModel):
    focus: str
    note: str


class BlueprintClassification(BaseModel):
    blueprint_key: str
    reason: str = ""


class GroundingReport(BaseModel):
    """Deterministic, non-LLM post-hoc check — never rewrites the
    answer, only reports. See services/interview/grounding.py.
    """
    unverifiable_claims: list[str] = []
    uses_flagged_project: bool = False


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
    # The model's own self-reported list of its least-verified
    # statements. Never trusted blindly — grounding.py independently
    # cross-checks the answer text regardless of what's reported here.
    claims_needing_verification: list[str] = []
    # Populated after generation by grounding.validate_answer() — never
    # set by the LLM itself; defaults empty until that pass runs.
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
    # Only populated on a response to POST /interview/correct, and only
    # when the correction looks like it fixes a durable fact.
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