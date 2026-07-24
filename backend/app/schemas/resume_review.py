from pydantic import BaseModel


class BulletIssue(BaseModel):
    type: str
    detail: str


class BulletReview(BaseModel):
    bullet_id: str
    source_type: str  # "experience" | "project"
    source_id: str
    source_label: str
    original: str
    issues: list[BulletIssue] = []
    rewrite: str | None = None
    rewrite_rationale: str = ""


class ATSFlag(BaseModel):
    type: str
    detail: str
    severity: str  # "high" | "medium" | "low"


class ResumeReviewStats(BaseModel):
    total_bullets: int
    flagged_bullets: int
    missing_metric_count: int
    weak_verb_count: int
    passive_voice_count: int


class ResumeReviewReport(BaseModel):
    overall_score: float
    summary: str
    strengths: list[str] = []
    top_priority_fixes: list[str] = []
    bullet_reviews: list[BulletReview] = []
    ats_flags: list[ATSFlag] = []
    stats: ResumeReviewStats
    analysis_degraded: bool = False


# --- Shape the LLM is asked to return (rewrites + narrative ONLY —
# it never decides whether an issue exists, that's given as fact) ---

class BulletRewriteSuggestion(BaseModel):
    bullet_id: str
    rewrite: str
    rationale: str


class LLMReviewOutput(BaseModel):
    summary: str
    strengths: list[str] = []
    top_priority_fixes: list[str] = []
    rewrites: list[BulletRewriteSuggestion] = []