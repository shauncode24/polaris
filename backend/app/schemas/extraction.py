from pydantic import BaseModel


class ExtractedExperience(BaseModel):
    role: str
    company: str
    start_date: str | None = None
    end_date: str | None = None
    stack: list[str] = []
    bullets: list[str] = []


class ExtractedProject(BaseModel):
    name: str
    description: str | None = None
    stack: list[str] = []


class ExtractionResult(BaseModel):
    experiences: list[ExtractedExperience] = []
    projects: list[ExtractedProject] = []
    skills: list[str] = []