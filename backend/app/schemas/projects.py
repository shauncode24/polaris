# from datetime import datetime

# from pydantic import BaseModel


# class ProjectCard(BaseModel):
#     id: str
#     name: str
#     tagline: str
#     description: str | None = None
#     stack: list[str] = []
#     capabilities: list[str] = []
#     engineering_tags: list[str] = []
#     tier: str = "Career Project"
#     is_featured: bool = False
#     status: str = "completed"
#     rating: float = 3.0
#     updated_at: datetime | None = None
#     repo_url: str | None = None
#     has_repo: bool = False
#     # NEW — explicit-linking fields
#     link_status: str = "unmatched"        # "confirmed" | "broken_link" | "suggested_match" | "unmatched"
#     github_repo_name: str | None = None


# class ProjectsStats(BaseModel):
#     total: int = 0
#     flagship: int = 0
#     technologies: int = 0
#     resume_coverage_pct: float = 0.0
#     github_coverage_pct: float = 0.0
#     capabilities: int = 0
#     connected_repositories: int = 0


# class ProjectsOverviewResponse(BaseModel):
#     stats: ProjectsStats = ProjectsStats()
#     projects: list[ProjectCard] = []


# class ComparisonMetric(BaseModel):
#     label: str
#     winner: str


# class ProjectComparison(BaseModel):
#     project_a: str
#     project_b: str
#     metrics: list[ComparisonMetric] = []
#     recommendation: str = ""


# class RecommendationItem(BaseModel):
#     text: str


# class MilestoneItem(BaseModel):
#     label: str
#     occurred_at: datetime


# # NEW — curation (keep/feature/hide)
# class CurationItem(BaseModel):
#     project_id: str
#     project_name: str
#     action: str  # "feature" | "keep" | "hide_suggested"
#     reason: str


# class CurationResult(BaseModel):
#     items: list[CurationItem] = []
#     dilution_warning: str | None = None


# # NEW — link suggestions
# class LinkSuggestion(BaseModel):
#     project_id: str
#     project_name: str
#     candidate_repo: str | None = None
#     confidence: str = "none"  # "exact" | "fuzzy" | "none"
#     other_candidates: list[str] = []


# class LinkProjectRequest(BaseModel):
#     repo_name: str


# class ProjectsInsightsResponse(BaseModel):
#     comparison: ProjectComparison | None = None
#     recommendations: list[RecommendationItem] = []
#     milestones: list[MilestoneItem] = []
#     source_coverage: dict = {}
#     curation: CurationResult = CurationResult()

from datetime import datetime

from pydantic import BaseModel


class ProjectCard(BaseModel):
    id: str
    name: str
    tagline: str
    description: str | None = None
    stack: list[str] = []
    capabilities: list[str] = []
    engineering_tags: list[str] = []
    tier: str = "Career Project"
    is_featured: bool = False
    status: str = "completed"
    rating: float = 3.0
    updated_at: datetime | None = None
    repo_url: str | None = None
    has_repo: bool = False
    matched_repo_name: str | None = None          # NEW — real repo linkage result
    claim_risk: str | None = None                  # NEW — "high" | "medium" | "undersold" | None
    abandonment_status: str | None = None           # NEW — "resume_it" | "retire_it" | None
    collaboration_mode: str | None = None            # NEW — "solo" | "mixed" | "collaborative"
    commit_hygiene_score: float | None = None         # NEW


class ProjectsStats(BaseModel):
    total: int = 0
    flagship: int = 0
    technologies: int = 0
    resume_coverage_pct: float = 0.0
    github_coverage_pct: float = 0.0
    capabilities: int = 0
    connected_repositories: int = 0
    claim_risk_count: int = 0  # NEW


class ProjectsOverviewResponse(BaseModel):
    stats: ProjectsStats = ProjectsStats()
    projects: list[ProjectCard] = []


class ComparisonMetric(BaseModel):
    label: str
    winner: str  # a project name, or "Tie"


class ProjectComparison(BaseModel):
    project_a: str
    project_b: str
    metrics: list[ComparisonMetric] = []
    recommendation: str = ""


class RecommendationItem(BaseModel):
    text: str
    impact: int = 0  # NEW — real score-point impact, not just an ordering hint


class MilestoneItem(BaseModel):
    label: str
    occurred_at: datetime


class ProjectsInsightsResponse(BaseModel):
    comparison: ProjectComparison | None = None
    recommendations: list[RecommendationItem] = []
    milestones: list[MilestoneItem] = []
    source_coverage: dict = {}