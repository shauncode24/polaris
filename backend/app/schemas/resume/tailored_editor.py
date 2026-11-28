"""What the tailored resume editor reads and sends.

The browser never sends a document back, only the user's choices, so the
original wording, the sources and the warnings on a rewrite can't be altered
from outside.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.resume.tailored import Decision, Section, SourceKind, TailoredResumeDocument
from app.schemas.resume.tailored_score import ResumeScore

# Generous: a project description written as one paragraph is a single line.
MAX_LINE_LENGTH = 2000


class EditorJob(BaseModel):
    id: str
    role: str | None = None
    company: str | None = None


class CitedEvidence(BaseModel):
    """What one source in the document points at, as the record reads now."""
    kind: SourceKind
    title: str
    origin: str  # where it came from, for the user: "Resume", "GitHub", ...
    detail: str | None = None  # for a cited bullet, its current wording
    url: str | None = None
    available: bool = True  # false once it has been removed or hidden


class SavedResume(BaseModel):
    version: int
    status: str
    created_at: datetime
    stale: bool  # the evidence has changed since this was generated
    document: TailoredResumeDocument
    evidence: dict[str, CitedEvidence]  # by source key: "kind:id:bullet", blanks for none
    score: ResumeScore


class ResumeEditorView(BaseModel):
    job: EditorJob
    versions: list[int]  # newest first
    resume: SavedResume | None = None  # none generated yet


class LineChange(BaseModel):
    """A change to one line. Fields that aren't sent stay as they are."""
    line_id: str
    decision: Decision | None = None  # on the rewrite
    edited: str | None = Field(default=None, max_length=MAX_LINE_LENGTH)  # null or blank removes the edit
    confirm_flags: bool = False  # required to accept a rewrite that has warnings


class ContactChange(BaseModel):
    """Contact details, kept for later resumes too. Fields that aren't sent
    stay as they are; null or blank removes one.
    """
    phone: str | None = Field(default=None, max_length=40)
    linkedin_url: str | None = Field(default=None, max_length=200)


class ResumeChanges(BaseModel):
    lines: list[LineChange] = Field(default=[], max_length=100)
    section_order: list[Section] | None = None
    contact: ContactChange | None = None
