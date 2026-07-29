"""Project Intelligence — the agent spec'd in the design doc (§6.1,
Phase 9) that was entirely absent from the codebase. Two modes:

- explain(project, framing) -> a per-project narrative synthesis
  (resume description + verified GitHub evidence + tier fused into one
  statement of what the project proves) plus a framing-specific answer
  (e.g. "as if interviewing at Amazon").
- compare(project, comparison_target) -> an honest comparison against
  a named external tool.

Both calls are fed ONLY the tightly-scoped, pre-verified knowledge
object built below — same pattern as github_knowledge.py — so the model
can never invent a fact about the project that doesn't exist. GitHub
evidence is included ONLY when the project has an explicit, confirmed
link (see services/projects/linking.py); this agent never falls back to
a name guess.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.facts import Project
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import ProjectIntelligenceReview
from app.models.structure import Capability, ProjectCapability, ProjectSkill, Skill
from app.prompts.project_intelligence import (
    PROJECT_COMPARE_SYSTEM_PROMPT,
    PROJECT_EXPLAIN_SYSTEM_PROMPT,
)
from app.schemas.project_intelligence import (
    ProjectComparisonLLMOutput,
    ProjectComparisonReport,
    ProjectIntelligenceLLMOutput,
    ProjectIntelligenceReport,
)


class ProjectIntelligenceError(Exception):
    """Raised when the project-intelligence LLM call fails or returns
    something we can't validate. Callers surface this as a failure
    (e.g. 502) rather than fabricating a narrative — same policy as
    the Interview Response Agent's InterviewGenerationError.
    """


async def build_project_knowledge_object(db: AsyncSession, user_id, project_id) -> dict | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        return None

    skill_rows = await db.execute(
        select(Skill.name)
        .join(ProjectSkill, ProjectSkill.skill_id == Skill.id)
        .where(ProjectSkill.project_id == project.id)
    )
    skills = [r[0] for r in skill_rows.all()]

    capability_rows = await db.execute(
        select(Capability.name)
        .join(ProjectCapability, ProjectCapability.capability_id == Capability.id)
        .where(ProjectCapability.project_id == project.id)
    )
    capabilities = [r[0] for r in capability_rows.all()]

    github_evidence = None
    if project.github_repo_name:
        gh_result = await db.execute(
            select(GithubProjectAnalysis).where(
                GithubProjectAnalysis.user_id == user_id,
                GithubProjectAnalysis.repo_name == project.github_repo_name,
            )
        )
        gh = gh_result.scalar_one_or_none()
        if gh is not None:
            github_evidence = {
                "technologies": gh.technologies,
                "capabilities": gh.capabilities,
                "tier": gh.tier,
                "quality_score": gh.quality_score,
                "activity_score": gh.activity_score,
                "has_readme": gh.has_readme,
                "has_tests": gh.has_tests,
                "has_ci": gh.has_ci,
                "commit_hygiene_score": gh.commit_hygiene_score,
                "collaboration_mode": gh.collaboration_mode,
                "architecture_assessment": gh.architecture_assessment,
            }

    return {
        "id": str(project.id),
        "name": project.name,
        "tagline": project.tagline,
        "description": project.description,
        "stack": project.stack or [],
        "resume_skills": skills,
        "capabilities": capabilities,
        "repo_url": project.repo_url,
        "github_linked": project.github_repo_name is not None,
        "github_evidence": github_evidence,
    }


async def generate_project_explanation(
    db: AsyncSession, user_id, project_id, framing: str
) -> ProjectIntelligenceReport:
    knowledge = await build_project_knowledge_object(db, user_id, project_id)
    if knowledge is None:
        raise ValueError("Project not found.")

    try:
        print(
            f"[TRACING] Requesting project explanation (project={knowledge['name']!r}, framing={framing!r})...",
            flush=True,
        )
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": PROJECT_EXPLAIN_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"project": knowledge, "framing": framing})},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw project explanation JSON:\n{content}", flush=True)
        llm_output = ProjectIntelligenceLLMOutput.model_validate(json.loads(content))
    except Exception as e:
        raise ProjectIntelligenceError(f"Project explanation LLM call failed: {e}") from e

    report = ProjectIntelligenceReport(
        **llm_output.model_dump(),
        project_id=str(project_id),
        framing=framing,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    db.add(ProjectIntelligenceReview(
        user_id=user_id,
        project_id=project_id,
        framing=framing,
        comparison_target=None,
        review_json=report.model_dump(mode="json"),
        created_at=datetime.now(timezone.utc),
    ))
    await db.flush()
    await db.commit()

    return report


async def generate_project_comparison(
    db: AsyncSession, user_id, project_id, comparison_target: str
) -> ProjectComparisonReport:
    knowledge = await build_project_knowledge_object(db, user_id, project_id)
    if knowledge is None:
        raise ValueError("Project not found.")

    try:
        print(
            f"[TRACING] Requesting project comparison (project={knowledge['name']!r}, target={comparison_target!r})...",
            flush=True,
        )
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": PROJECT_COMPARE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({
                    "project": knowledge, "comparison_target": comparison_target,
                })},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw project comparison JSON:\n{content}", flush=True)
        llm_output = ProjectComparisonLLMOutput.model_validate(json.loads(content))
    except Exception as e:
        raise ProjectIntelligenceError(f"Project comparison LLM call failed: {e}") from e

    report = ProjectComparisonReport(
        **llm_output.model_dump(),
        project_id=str(project_id),
        comparison_target=comparison_target,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    db.add(ProjectIntelligenceReview(
        user_id=user_id,
        project_id=project_id,
        framing="__compare__",
        comparison_target=comparison_target,
        review_json=report.model_dump(mode="json"),
        created_at=datetime.now(timezone.utc),
    ))
    await db.flush()
    await db.commit()

    return report


async def get_project_intelligence_history(db: AsyncSession, user_id, project_id) -> list[dict]:
    result = await db.execute(
        select(ProjectIntelligenceReview)
        .where(ProjectIntelligenceReview.user_id == user_id)
        .where(ProjectIntelligenceReview.project_id == project_id)
        .order_by(ProjectIntelligenceReview.created_at.desc())
        .limit(10)
    )
    return [row.review_json for row in result.scalars().all()]