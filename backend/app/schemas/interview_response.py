from datetime import datetime

from pydantic import BaseModel


class InterviewAskRequest(BaseModel):
    question: str
    target_role: str | None = None
    target_company: str | None = None


class CoachingNote(BaseModel):
    focus: str   # e.g. "Metrics", "Pacing", "Structure", "Technical depth"
    note: str


class BlueprintClassification(BaseModel):
    """Output of the cheap pre-classification pass — picks which single
    blueprint from the library to hand to the (much more expensive)
    generation call, instead of sending all ~24 blueprints every time.
    """
    blueprint_key: str
    reason: str = ""


class InterviewLLMOutput(BaseModel):
    question_type: str
    blueprint_used: str = ""     # which library key was followed, or "custom: <reason>"
    competencies: list[str] = []
    stories_used: list[str] = []
    answer: str = ""
    answer_short: str = ""
    follow_up_questions: list[str] = []
    coaching: list[CoachingNote] = []
    insufficient_context: bool = False
    context_note: str = ""


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
    created_at: datetime | None = None