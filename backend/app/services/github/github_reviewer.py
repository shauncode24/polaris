import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.inference import GithubPortfolioReview
from app.prompts.github_review import GITHUB_REVIEW_SYSTEM_PROMPT
from app.schemas.github_review import GithubPortfolioReviewLLMOutput, GithubPortfolioReviewReport
from app.services.github.github_knowledge import build_github_knowledge_object


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
        print("[TRACING] Requesting GitHub portfolio review from LLM...", flush=True)
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
        print(f"[TRACING] Raw GitHub portfolio review JSON:\n{content}", flush=True)
        llm_output = GithubPortfolioReviewLLMOutput.model_validate(json.loads(content))
    except Exception as e:
        print(f"[TRACING] GitHub portfolio review degraded, using fallback: {e}", flush=True)
        llm_output = _fallback_report(knowledge)
        degraded = True

    # Never trust flagship project names blindly — drop anything that
    # isn't a real repo we actually handed the model (same rule
    # gap_analysis.py applies to priority_order).
    real_repo_names = {r["name"] for r in knowledge["repositories"]}
    llm_output.flagship_projects = [
        fp for fp in llm_output.flagship_projects if fp.name in real_repo_names
    ]

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