"""GitHub portfolio review — hiring-manager-facing LLM interpretation.

Audience: the candidate wanting honest, role-specific hiring feedback on
their GitHub portfolio (role fit, recruiter read, resume integration).

Distinct from PortfolioNarrativeReview (projects/portfolio_narrative.py),
which answers the same surface question from an engineering self-knowledge
angle (testing/collaboration patterns, specialization/weakness) using raw
GithubProjectAnalysis rows rather than the condensed knowledge object.

Guardrails applied here (same pattern as resume/reviewer.py):
  1. flagship_projects filtered to real repo names only
  2. skill_confidence_explanations filtered to real technology names only
  3. role_fit is now sourced ENTIRELY from the single shared, entirely-
     LLM-generated services/identity/role_fit.get_role_fit(scope="github_only")
     (Engineering Identity fix #2) — the deterministic "anchor percentage"
     that used to clamp the model's own rating has been removed. Role-fit
     is not, and must never again be, partly deterministic.
"""
import logging
from datetime import datetime, timezone

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.inference import GithubPortfolioReview
from app.prompts.github_review import GITHUB_REVIEW_SYSTEM_PROMPT
from app.schemas.github_review import GithubPortfolioReviewLLMOutput, GithubPortfolioReviewReport
from app.services.github.github_knowledge import build_github_knowledge_object
from app.services.identity.role_fit import get_role_fit
from app.services.identity.role_fit_scoping import build_scoped_skill_evidence, GITHUB_SOURCE_TYPES

logger = logging.getLogger(__name__)


class GithubReviewError(Exception):
    """Raised when the portfolio-review LLM call fails or returns
    something we can't validate. Same graceful-degradation pattern as
    ReviewGenerationError in resume/reviewer.py — callers fall back to a
    deterministic summary instead of crashing the whole endpoint.
    """


def _fallback_report(knowledge: dict) -> GithubPortfolioReviewLLMOutput:
    repos = knowledge.get("repositories", [])
    top = repos[:3]
    return GithubPortfolioReviewLLMOutput(
        engineering_assessment=(
            f"Portfolio review is temporarily unavailable. Deterministic data shows "
            f"{knowledge.get('summary', {}).get('repos_synced', 0)} synced repositories covering "
            f"{', '.join(knowledge.get('all_technologies', [])[:6]) or 'no detected technologies'}."
        ),
        flagship_projects=[
            {"name": r["name"], "reason": "Highest combined quality/activity score in your synced repositories."}
            for r in top
        ],
        recruiter_perspective={
            "notices": [f"{knowledge.get('summary', {}).get('repos_synced', 0)} repositories synced"],
            "decision": "Narrative review unavailable right now — see the repository explorer for real data.",
        },
    )


async def generate_github_portfolio_review(db: AsyncSession, user_id) -> GithubPortfolioReviewReport:
    knowledge = await build_github_knowledge_object(db, user_id)
    if knowledge is None or not knowledge.get("repositories"):
        raise ValueError("No synced GitHub data found for this user — run a GitHub sync first.")

    degraded = False
    try:
        logger.info("Requesting GitHub portfolio review from LLM...")
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": GITHUB_REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(knowledge)},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        content = response.choices[0].message.content
        logger.debug("Raw GitHub portfolio review JSON: %s", content)
        llm_output = GithubPortfolioReviewLLMOutput.model_validate(json.loads(content))
    except Exception as e:
        logger.warning("GitHub portfolio review degraded, using fallback: %s", e)
        llm_output = _fallback_report(knowledge)
        degraded = True

    real_repo_names = {r["name"] for r in knowledge["repositories"]}
    llm_output.flagship_projects = [
        fp for fp in llm_output.flagship_projects if fp.name in real_repo_names
    ]

    # Role-fit: ALWAYS sourced from the single shared, entirely-LLM-
    # generated function, scoped to GitHub-only evidence — never from
    # whatever (if anything) the main review call above returned, and
    # never clamped against a deterministic anchor.
    github_scoped_evidence = await build_scoped_skill_evidence(db, GITHUB_SOURCE_TYPES)
    llm_output.role_fit = await get_role_fit(github_scoped_evidence, scope="github_only")

    real_tech_names = set(knowledge.get("all_technologies", []))
    original_skill_count = len(llm_output.skill_confidence_explanations)
    llm_output.skill_confidence_explanations = [
        sce for sce in llm_output.skill_confidence_explanations if sce.skill in real_tech_names
    ]
    dropped_skills = original_skill_count - len(llm_output.skill_confidence_explanations)
    if dropped_skills:
        logger.warning(
            "Dropped %d skill_confidence_explanations with non-verified skill names",
            dropped_skills,
        )

    report = GithubPortfolioReviewReport(
        **llm_output.model_dump(),
        generated_at=datetime.now(timezone.utc).isoformat(),
        analysis_degraded=degraded,
    )

    review_row = GithubPortfolioReview(
        user_id=user_id,
        review_json=report.model_dump(mode="json"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(review_row)
    await db.flush()
    await db.commit()

    return report