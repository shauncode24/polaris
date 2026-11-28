"""The structured form of a resume tailored to one job. It is what gets
generated, checked, edited, saved and exported.

Everything stated in it points at the evidence it came from (`sources`), so
that each claim can be checked against the user's record. The header is the
exception: it is the user's own contact details.

A line keeps the evidence's wording, any AI rewrite of it, and the user's
decision. A rewrite appears on the resume only once the user accepts it.
"""
import uuid
from datetime import date
from typing import Literal, get_args

from pydantic import BaseModel, Field, computed_field, model_validator

SCHEMA_VERSION = 1

# The kinds match `SkillEvidence.source_type`, plus education rows.
SourceKind = Literal[
    "experience", "project", "education", "certificate", "github_repo", "linkedin_profile", "leetcode_tag",
]
Section = Literal["summary", "experience", "projects", "education", "skills"]
Decision = Literal["pending", "accepted", "rejected"]


class SourceRef(BaseModel):
    """One item in the user's evidence record."""
    kind: SourceKind
    id: uuid.UUID | None = None  # LeetCode practice has no single row
    bullet: int | None = Field(default=None, ge=0)  # which of the row's bullets

    @model_validator(mode="after")
    def _row_is_named(self):
        if self.id is None and self.kind != "leetcode_tag":
            raise ValueError(f"a '{self.kind}' source needs the id of its row")
        return self


Sources = list[SourceRef]


def _new_id() -> str:
    return uuid.uuid4().hex


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


class ResumeLine(BaseModel):
    """A bullet, or the summary."""
    id: str = Field(default_factory=_new_id, min_length=1)  # stays the same through edits and reordering
    original: str | None = None  # as the evidence words it; a generated summary has none
    rewrite: str | None = None  # the AI's wording for this job
    decision: Decision = "pending"  # on the rewrite
    edited: str | None = None  # the user's own wording, which wins over both
    flags: list[str] = []  # claims in the rewrite the evidence doesn't support
    sources: Sources = Field(min_length=1)

    @model_validator(mode="after")
    def _says_something(self):
        if not any(_has_text(t) for t in (self.original, self.rewrite, self.edited)):
            raise ValueError("a line needs some text")
        return self

    @computed_field
    @property
    def text(self) -> str:
        """What appears on the resume; empty when nothing has been approved."""
        if _has_text(self.edited):
            return self.edited.strip()
        if self.decision == "accepted" and _has_text(self.rewrite):
            return self.rewrite.strip()
        return (self.original or "").strip()


class Link(BaseModel):
    label: str = Field(min_length=1)
    url: str = Field(min_length=1)


class Header(BaseModel):
    full_name: str = Field(min_length=1)
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[Link] = []


class ExperienceEntry(BaseModel):
    role: str = Field(min_length=1)
    company: str = Field(min_length=1)
    start_date: date | None = None
    end_date: date | None = None
    bullets: list[ResumeLine] = []
    sources: Sources = Field(min_length=1)


class ProjectEntry(BaseModel):
    name: str = Field(min_length=1)
    url: str | None = None
    technologies: list[str] = []
    bullets: list[ResumeLine] = []
    sources: Sources = Field(min_length=1)


class EducationEntry(BaseModel):
    institution: str = Field(min_length=1)
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    bullets: list[ResumeLine] = []
    sources: Sources = Field(min_length=1)


class SkillEntry(BaseModel):
    name: str = Field(min_length=1)  # as written on the resume
    canonical: str = Field(min_length=1)  # as the evidence and job requirements name it
    sources: Sources = Field(min_length=1)


class TailoredResumeDocument(BaseModel):
    """Entries and lines appear in list order; sections in `section_order`."""
    schema_version: Literal[1] = SCHEMA_VERSION
    header: Header
    summary: ResumeLine | None = None
    experience: list[ExperienceEntry] = []
    projects: list[ProjectEntry] = []
    education: list[EducationEntry] = []
    skills: list[SkillEntry] = []
    section_order: list[Section] = Field(default_factory=lambda: list(get_args(Section)))

    def lines(self) -> list[ResumeLine]:
        entries = [*self.experience, *self.projects, *self.education]
        summary = [self.summary] if self.summary else []
        return summary + [line for entry in entries for line in entry.bullets]

    @model_validator(mode="after")
    def _consistent(self):
        ids = [line.id for line in self.lines()]
        if len(ids) != len(set(ids)):
            raise ValueError("two lines have the same id")
        if sorted(self.section_order) != sorted(get_args(Section)):
            raise ValueError("section_order must list every section once")
        return self


class RankedEvidence(BaseModel):
    """How one experience or project ranked for the job."""
    id: str
    type: Literal["experience", "project"]
    label: str
    relevance_score: float
    matched_skills: list[str] = []
    claim_risk: str | None = None  # "high" | "medium": its score was reduced for this
    selected: bool


class Selection(BaseModel):
    document: TailoredResumeDocument
    ranking: list[RankedEvidence]  # most relevant first
