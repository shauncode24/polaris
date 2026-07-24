from pydantic import BaseModel


class SkillClassification(BaseModel):
    raw: str
    canonical: str | None = None
    is_valid_skill: bool


class SkillClassificationBatch(BaseModel):
    results: list[SkillClassification]