from pydantic import BaseModel


class ExtractedExperience(BaseModel):
    role: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    stack: list[str] = []
    bullets: list[str] = []


class ExtractedProject(BaseModel):
    name: str | None = None
    description: str | None = None
    stack: list[str] = []


class ExtractedEducation(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    details: list[str] = []  # GPA, honors, relevant coursework, etc. — free text lines


class ExtractionResult(BaseModel):
    experiences: list[ExtractedExperience] = []
    projects: list[ExtractedProject] = []
    education: list[ExtractedEducation] = []
    skills: list[str] = []