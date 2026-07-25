from datetime import datetime

from pydantic import BaseModel


class InterviewAskRequest(BaseModel):
    question: str
    target_role: str | None = None
    target_company: str | None = None


# --- Shape the LLM is asked to return. Nothing here is pre-computed —
# question_type, competencies, story selection, and the insufficient-
# context judgment are ALL decisions the model makes itself from the
# raw profile it's given. ---

class InterviewLLMOutput(BaseModel):
    question_type: str
    competencies: list[str] = []
    stories_used: list[str] = []
    answer: str = ""
    answer_short: str = ""
    follow_up_questions: list[str] = []
    coaching: list[str] = []
    insufficient_context: bool = False
    context_note: str = ""


class InterviewResponseOutput(BaseModel):
    response_id: str | None = None
    question: str
    question_type: str
    answer: str
    answer_short: str = ""
    stories_used: list[str] = []
    competencies: list[str] = []
    follow_up_questions: list[str] = []
    coaching: list[str] = []
    insufficient_context: bool = False
    context_note: str = ""
    created_at: datetime | None = None