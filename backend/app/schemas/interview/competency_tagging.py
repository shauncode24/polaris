# backend/app/schemas/interview/competency_tagging.py
from pydantic import BaseModel


class CompetencyTagResult(BaseModel):
    key: str
    tags: list[str] = []


class CompetencyTagBatch(BaseModel):
    results: list[CompetencyTagResult] = []