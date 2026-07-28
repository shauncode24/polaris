from pydantic import BaseModel


class OffNarrativeBullet(BaseModel):
    bullet_id: str
    source_label: str
    categories: list[str] = []


class CoherenceFacts(BaseModel):
    category_distribution: dict[str, float] = {}
    dominant_category: str | None = None
    target_role: str | None = None
    target_role_categories: list[str] = []
    target_role_alignment_pct: float | None = None
    off_narrative_bullets: list[OffNarrativeBullet] = []


class CoherenceLLMOutput(BaseModel):
    argued_role: str = ""
    positioning_statement: str = ""
    strengths_for_this_story: list[str] = []
    weakens_the_story: list[str] = []
    recommended_cuts: list[str] = []  # bullet_ids, validated against real input
    recommendation: str = ""


class CoherenceReport(BaseModel):
    facts: CoherenceFacts
    dilution: dict = {}
    narrative: CoherenceLLMOutput
    analysis_degraded: bool = False