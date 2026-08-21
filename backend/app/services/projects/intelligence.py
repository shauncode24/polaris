import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.facts import Project
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import ProjectIntelligenceReview
from app.prompts.projects.project_intelligence import PROJECT_INTELLIGENCE_SYSTEM_PROMPT
from app.schemas.projects.project_intelligence import ProjectIntelligenceLLMOutput, ProjectIntelligenceReport
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.projects.repo_linking import match_project_to_repo

logger = logging.getLogger(__name__)


async def build_project_context(db: AsyncSession, user_id, project_id) -> dict | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        return None

    analysis_result = await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)
    )
    analysis_by_repo = {a.repo_name: a for a in analysis_result.scalars().all()}
    matched_repo_name = match_project_to_repo(project.name, project.repo_url, list(analysis_by_repo.keys()))
    matched = analysis_by_repo.get(matched_repo_name) if matched_repo_name else None

    return {
        "name": project.name,
        "description": project.description,
        "stack": project.stack or [],
        "has_repo_match": matched is not None,
        "verified": {
            "technologies": matched.technologies if matched else [],
            "capabilities": matched.capabilities if matched else [],
            "architecture_assessment": matched.architecture_assessment if matched else None,
            "has_tests": matched.has_tests if matched else None,
            "has_ci": matched.has_ci if matched else None,
            "quality_score": matched.quality_score if matched else None,
            "activity_score": matched.activity_score if matched else None,
            "collaboration": (
                {"mode": matched.collaboration_mode, "score": matched.collaboration_score} if matched else None
            ),
            "commit_hygiene_score": matched.commit_hygiene_score if matched else None,
        } if matched else {},
    }


async def _build_target_job_intelligence(db: AsyncSession, job_intelligence_id: str | None) -> dict | None:
    """NEW — optional grounding in a real Job Intelligence profile
    (design doc §6.2). Only exposes the fields the framing prompt can
    actually act on."""
    if not job_intelligence_id:
        return None
    profile = await get_job_intelligence(db, UUID(job_intelligence_id))
    if profile is None:
        return None
    return {
        "role": profile.role,
        "company": profile.company,
        "seniority_signal": profile.seniority_signal.model_dump(),
        "architecture_topics": profile.architecture_topics,
        "required_technologies": profile.all_required_technologies,
    }


def _normalize_comparison_target(comparison_target: str | None) -> str:
    return (comparison_target or "").strip()


async def get_cached_project_intelligence(
    db: AsyncSession, project_id, framing: str, comparison_target: str | None
) -> ProjectIntelligenceReport | None:
    normalized_target = _normalize_comparison_target(comparison_target)
    result = await db.execute(
        select(ProjectIntelligenceReview)
        .where(ProjectIntelligenceReview.project_id == project_id)
        .where(ProjectIntelligenceReview.framing == framing)
        .where(ProjectIntelligenceReview.comparison_target == normalized_target)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return ProjectIntelligenceReport.model_validate(row.report_json)


async def _persist_project_intelligence(
    db: AsyncSession, user_id, project_id, framing: str, comparison_target: str | None,
    report: ProjectIntelligenceReport,
) -> None:
    normalized_target = _normalize_comparison_target(comparison_target)
    payload = report.model_dump(mode="json")
    stmt = (
        pg_insert(ProjectIntelligenceReview)
        .values(
            user_id=user_id, project_id=project_id, framing=framing,
            comparison_target=normalized_target, report_json=payload,
            created_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            constraint="uq_intelligence_project_framing",
            set_={"report_json": payload, "created_at": datetime.now(timezone.utc)},
        )
    )
    await db.execute(stmt)
    await db.commit()


async def generate_project_intelligence(
    db: AsyncSession, user_id, project_id, framing: str, comparison_target: str | None,
    job_intelligence_id: str | None = None,
) -> ProjectIntelligenceReport:
    """job_intelligence_id is NOT part of the cache key (framing +
    comparison_target still are, unchanged) — this is a deliberate,
    documented limitation for now: regenerating with a different
    job_intelligence_id for the same framing overwrites the cached
    report. Extending the cache key would need its own migration
    (uq_intelligence_project_framing), left for a follow-up.
    """
    project_context = await build_project_context(db, user_id, project_id)
    if project_context is None:
        raise ValueError("Project not found.")

    target_job_intelligence = await _build_target_job_intelligence(db, job_intelligence_id)
    payload = {
        **project_context, "framing": framing, "comparison_target": comparison_target,
        "target_job_intelligence": target_job_intelligence,
    }

    try:
        print(
            f"[TRACING] Requesting project intelligence for '{project_context['name']}' (framing={framing!r})...",
            flush=True,
        )
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": PROJECT_INTELLIGENCE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        logger.debug("Raw project intelligence JSON:\n%s", content)
        llm_output = ProjectIntelligenceLLMOutput.model_validate(json.loads(content))
        degraded = False
    except Exception as e:
        logger.warning("Project intelligence degraded, using fallback: %s", e)
        llm_output = ProjectIntelligenceLLMOutput(
            framing=framing,
            explanation=f"Detailed explanation is temporarily unavailable for {project_context['name']}.",
            insufficient_context=not project_context["stack"] and not project_context["description"],
            context_note="Narrative generation failed; showing verified facts only.",
        )
        degraded = True

    report = ProjectIntelligenceReport(
        **llm_output.model_dump(),
        project_name=project_context["name"],
        generated_at=datetime.now(timezone.utc).isoformat(),
        analysis_degraded=degraded,
    )
    await _persist_project_intelligence(db, user_id, project_id, framing, comparison_target, report)
    return report