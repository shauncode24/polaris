from pydantic import BaseModel, field_validator

from app.core.settings import settings


class ExtractedLinkedInExperience(BaseModel):
    role: str | None = None
    company: str | None = None
    # Kept as LinkedIn's own raw string (e.g. "Jan 2022 - Present"),
    # never parsed into a real date — same simplification the resume
    # extraction pipeline already makes for its own date fields.
    date_range: str | None = None
    bullets: list[str] = []


class ExtractedLinkedInEducation(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    date_range: str | None = None


class ExtractedLinkedInProfile(BaseModel):
    headline: str | None = None
    about: str | None = None
    experience: list[ExtractedLinkedInExperience] = []
    education: list[ExtractedLinkedInEducation] = []
    skills: list[str] = []
    achievements: list[str] = []


class LinkedInIngestRequest(BaseModel):
    raw_text: str

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("raw_text must not be empty.")
        if len(stripped) > settings.max_paste_text_chars:
            raise ValueError(
                f"raw_text exceeds the maximum allowed length of {settings.max_paste_text_chars} characters."
            )
        return v


class LinkedInIngestResult(BaseModel):
    linkedin_profile_id: str
    experiences_created: int
    education_created: int
    skills_processed: int
    experiences_deduped: int
    education_deduped: int


class LinkedInWorkspace(BaseModel):
    has_data: bool
    headline: str | None = None
    about: str | None = None
    skills: list[str] = []
    achievements: list[str] = []
    experience_count: int = 0
    education_count: int = 0
    created_at: str | None = None