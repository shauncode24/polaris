from datetime import datetime

from pydantic import BaseModel


class ProjectCard(BaseModel):
    id: str
    name: str
    tagline: str
    description: str | None = None
    stack: list[str] = []
    capabilities: list[str] = []
    is_featured: bool = False
    status: str = "completed"  # "ongoing" | "completed"
    rating: float = 3.0
    updated_at: datetime | None = None
    repo_url: str | None = None
    has_repo: bool = False


class ProjectsStats(BaseModel):
    total: int = 0
    featured: int = 0
    technologies: int = 0
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