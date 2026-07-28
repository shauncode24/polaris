from datetime import datetime

from pydantic import BaseModel


class ProjectCard(BaseModel):
    id: str
    name: str
    tagline: str
    description: str | None = None
    stack: list[str] = []
    capabilities: list[str] = []
    engineering_tags: list[str] = []      # NEW — replaces star rating as the headline signal
    tier: str = "Career Project"          # NEW — Flagship / Career / Learning / Prototype / Archived
    is_featured: bool = False
    status: str = "completed"
    rating: float = 3.0                   # kept internally for sorting only; not shown as stars anymore
    updated_at: datetime | None = None
    repo_url: str | None = None
    has_repo: bool = False


class ProjectsStats(BaseModel):
    total: int = 0
    flagship: int = 0                     # NEW
    technologies: int = 0
    resume_coverage_pct: float = 0.0      # NEW
    github_coverage_pct: float = 0.0      # NEW
    capabilities: int = 0
    connected_repositories: int = 0


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


class MilestoneItem(BaseModel):
    label: str
    occurred_at: datetime


class ProjectsInsightsResponse(BaseModel):
    comparison: ProjectComparison | None = None
    recommendations: list[RecommendationItem] = []
    milestones: list[MilestoneItem] = []
    source_coverage: dict = {}