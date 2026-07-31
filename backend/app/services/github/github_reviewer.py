"""GitHub portfolio review \u2014 hiring-manager-facing LLM interpretation.

Audience: the candidate wanting honest, role-specific hiring feedback on
their GitHub portfolio (role fit, recruiter read, resume integration).

Distinct from PortfolioNarrativeReview (projects/portfolio_narrative.py),
which answers the same surface question from an engineering self-knowledge
angle (testing/collaboration patterns, specialization/weakness) using raw
GithubProjectAnalysis rows rather than the condensed knowledge object.
The two intentionally coexist: merging them would create one monster
prompt and couple portfolio narrative to this module's DB dependency chain.

Guardrails applied here (same pattern as resume/reviewer.py):
  1. flagship_projects filtered to real repo names only
  2. role_fit filtered to ROLE_ARCHETYPES canonical names only
  3. skill_confidence_explanations filtered to real technology names only
  4. role_fit grounded with a deterministic code-computed anchor injected
     into the knowledge object before the LLM call
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
from app.services.resume.analysis.role_fit import ROLE_ARCHETYPES, compute_role_fit

logger = logging.getLogger(__name__)

# Canonical role name set \u2014 any LLM-invented role name outside this set
# is silently dropped, same as the flagship_projects guard above.
_VALID_ROLE_NAMES = set(ROLE_ARCHETYPES.keys())


class GithubReviewError(Exception):
    """Raised when the portfolio-review LLM call fails or returns
    something we can't validate. Same graceful-degradation pattern as
    ReviewGenerationError in resume/reviewer.py \u2014 callers fall back to a
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
            "decision": "Narrative review unavailable right now \u2014 see the repository explorer for real data.",
        },
    )


def _build_role_fit_anchor(repositories: list[dict]) -> list[dict]:
    """Compute a deterministic role-fit baseline from the repo technologies
    and capabilities in the knowledge object. This is the same formula used
    by resume/analysis/role_fit.compute_role_fit() \u2014 injected into the
    knowledge object so the LLM has a code-computed anchor to interpret
    instead of inventing ratings from scratch.
    """
    # Collect all unique technologies and capabilities across repos as
    # pseudo-skill entries that compute_role_fit() can categorise.
    all_tech_and_caps: set[str] = set()
    for repo in repositories:
        for t in repo.get("technologies", []) or []:
            all_tech_and_caps.add(t.lower())
        for c in repo.get("capabilities", []) or []:
            all_tech_and_caps.add(c.lower())

    # Shape matches what compute_role_fit expects: list of {canonical, confidence}
    pseudo_skills = [{"canonical": t, "name": t, "confidence": "medium"} for t in all_tech_and_caps]
    return compute_role_fit(pseudo_skills)


async def generate_github_portfolio_review(db: AsyncSession, user_id) -> GithubPortfolioReviewReport:
    knowledge = await build_github_knowledge_object(db, user_id)
    if knowledge is None or not knowledge.get("repositories"):
        raise ValueError("No synced GitHub data found for this user \u2014 run a GitHub sync first.")

    # Compute deterministic role-fit anchor and inject before LLM call.
    # This gives the model a grounding baseline and lets us validate
    # its output against a real, explainable computation.
    role_fit_anchor = _build_role_fit_anchor(knowledge["repositories"])
    knowledge["role_fit_anchor"] = role_fit_anchor

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

    # --- Post-hoc validation: same "never trust the LLM on names" rule
    # that flagship_projects already gets, now applied to role_fit and
    # skill_confidence_explanations too. ---

    # 1. flagship_projects: must reference a real synced repo.
    real_repo_names = {r["name"] for r in knowledge["repositories"]}
    llm_output.flagship_projects = [
        fp for fp in llm_output.flagship_projects if fp.name in real_repo_names
    ]

    # 2. role_fit: must use one of the ROLE_ARCHETYPES canonical role names.
    #    LLM-invented roles (e.g. "DevOps" instead of "DevOps / Platform",
    #    "AI Engineer" instead of "AI/ML Engineer") are silently dropped.
    original_role_count = len(llm_output.role_fit)
    llm_output.role_fit = [rf for rf in llm_output.role_fit if rf.role in _VALID_ROLE_NAMES]
    dropped_roles = original_role_count - len(llm_output.role_fit)
    if dropped_roles:
        logger.warning(
            "Dropped %d role_fit entries with non-canonical role names (valid: %s)",
            dropped_roles,
            sorted(_VALID_ROLE_NAMES),
        )

    # 3. skill_confidence_explanations: skill name must appear in all_technologies.
    #    The LLM is only given technologies that code has already verified
    #    exist \u2014 any name outside that set is hallucinated.
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