"""Real per-project timeline, replacing the old account-level sync-event
feed (which only ever told the user "GitHub sync completed" — nothing
about their PROJECTS specifically). Reads consecutive PortfolioAnalysis
rows (now actually written by github_sync.py — see the wiring change
there) and surfaces their real, dated observations. This is genuine
project-level memory instead of account-level noise wearing a project
page's costume.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_analysis import PortfolioAnalysis
from app.models.inference import ProjectClaimAuditReview
from app.models.facts import Project
from app.schemas.projects.projects import MilestoneItem

MAX_SNAPSHOTS = 6


async def build_recent_milestones(db: AsyncSession, user_id, limit: int = 5) -> list[MilestoneItem]:
    result = await db.execute(
        select(PortfolioAnalysis)
        .where(PortfolioAnalysis.user_id == user_id)
        .order_by(PortfolioAnalysis.computed_at.desc())
        .limit(MAX_SNAPSHOTS)
    )
    snapshots = list(result.scalars().all())
    if not snapshots:
        snapshots = []

    milestones: list[MilestoneItem] = []
    for snapshot in snapshots:
        for obs in (snapshot.observations or [])[:3]:
            milestones.append(MilestoneItem(label=obs, occurred_at=snapshot.computed_at))

    # Real project-scoped events (claim-audit risk findings) — not just
    # account-wide GitHub-sync observations.
    proj_result = await db.execute(select(Project.id, Project.name).where(Project.user_id == user_id))
    projects_by_id = {pid: name for pid, name in proj_result.all()}
    if projects_by_id:
        audit_result = await db.execute(
            select(ProjectClaimAuditReview)
            .where(ProjectClaimAuditReview.project_id.in_(projects_by_id.keys()))
            .order_by(ProjectClaimAuditReview.created_at.desc())
            .limit(limit)
        )
        for row in audit_result.scalars().all():
            narrative = (row.report_json or {}).get("narrative", {})
            risk = narrative.get("risk_level")
            if risk in ("high", "medium"):
                project_name = projects_by_id.get(row.project_id, "a project")
                milestones.append(MilestoneItem(
                    label=f"Claim audit flagged {risk} risk on {project_name}: {narrative.get('headline', '')}",
                    occurred_at=row.created_at,
                ))

    milestones.sort(key=lambda m: m.occurred_at, reverse=True)
    return milestones[:limit]