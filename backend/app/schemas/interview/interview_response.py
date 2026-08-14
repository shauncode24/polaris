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
    """Deterministic, non-LLM post-hoc check — never rewrites the
    answer, only reports. See services/interview/grounding.py.
    """
    unverifiable_claims: list[str] = []
    uses_flagged_project: bool = False
    # NEW (Phase 0, plan §H) — real/likely-fabricated entity names found
    # by scanning the full answer prose for known placeholder patterns
    # (e.g. "Project Alpha", "Innovate Solutions"), independent of what
    # the model self-reported in stories_used. Advisory only in Phase 0
    # — nothing blocks or regenerates on this yet (that's Phase 1's
    # pre-prose plan-validation stage).
    possible_fabricated_entities: list[str] = []


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