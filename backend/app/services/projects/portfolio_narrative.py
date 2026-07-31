import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import PortfolioNarrativeReview
from app.prompts.portfolio_narrative import PORTFOLIO_NARRATIVE_SYSTEM_PROMPT
from app.schemas.project_intelligence import PortfolioNarrativeLLMOutput, PortfolioNarrativeReport

MIN_VERIFIED_PROJECTS_FOR_NARRATIVE = 2


async def _build_portfolio_facts(db: AsyncSession, user_id) -> dict | None:
    result = await db.execute(
        select(GithubProjectAnalysis)
        .where(GithubProjectAnalysis.user_id == user_id)
        .where(GithubProjectAnalysis.is_fork.is_(False))
    )
    analyses = list(result.scalars().all())
    if len(analyses) < MIN_VERIFIED_PROJECTS_FOR_NARRATIVE:
        return None

    total = len(analyses)
    tested = sum(1 for a in analyses if a.has_tests)
    ci = sum(1 for a in analyses if a.has_ci)

    collab_counts: dict[str, int] = {}
    for a in analyses:
        collab_counts[a.collaboration_mode] = collab_counts.get(a.collaboration_mode, 0) + 1

    avg_hygiene = round(sum(a.commit_hygiene_score for a in analyses) / total, 1)

    tech_counts: dict[str, int] = {}
    for a in analyses:
        for t in (a.technologies or []):
            tech_counts[t] = tech_counts.get(t, 0) + 1

    depth_counts: dict[str, int] = {}
    for a in analyses:
        if a.architecture_assessment:
            label = a.architecture_assessment.get("depth_label")
            if label:
                depth_counts[label] = depth_counts.get(label, 0) + 1

    return {
        "total_verified_projects": total,
        "tested_projects": tested,
        "ci_projects": ci,
        "collaboration_distribution": collab_counts,
        "average_commit_hygiene": avg_hygiene,
        "technology_distribution": dict(sorted(tech_counts.items(), key=lambda kv: kv[1], reverse=True)[:15]),
        "architecture_depth_distribution": depth_counts,
    }


async def get_latest_portfolio_narrative(db: AsyncSession, user_id) -> PortfolioNarrativeReport | None:
    """Read-back for the most recent generation — append-only history,
    same pattern as GithubPortfolioReview/LeetcodePortfolioReview. None
    if a narrative has never been generated for this user.
    """
    result = await db.execute(
        select(PortfolioNarrativeReview)
        .where(PortfolioNarrativeReview.user_id == user_id)
        .order_by(PortfolioNarrativeReview.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return PortfolioNarrativeReport.model_validate(row.report_json)


async def _persist_portfolio_narrative(db: AsyncSession, user_id, report: PortfolioNarrativeReport) -> None:
    row = PortfolioNarrativeReview(
        user_id=user_id, report_json=report.model_dump(mode="json"), created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    await db.commit()


async def generate_portfolio_narrative(db: AsyncSession, user_id) -> PortfolioNarrativeReport:
    facts = await _build_portfolio_facts(db, user_id)
    if facts is None:
        report = PortfolioNarrativeReport(
            eligible=False,
            narrative="Not enough verified projects yet to generate a portfolio-wide narrative — sync more repositories.",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        # Not persisted — an "ineligible" read isn't a real generation
        # worth keeping in history; the next real generation should be
        # what's read back once the user has enough synced repos.
        return report

    degraded = False
    try:
        print("[TRACING] Requesting portfolio-wide narrative from LLM...", flush=True)
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": PORTFOLIO_NARRATIVE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(facts)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw portfolio narrative JSON:\n{content}", flush=True)
        llm_output = PortfolioNarrativeLLMOutput.model_validate(json.loads(content))
    except Exception as e:
        print(f"[TRACING] Portfolio narrative degraded, using fallback: {e}", flush=True)
        tested_pct = round((facts["tested_projects"] / facts["total_verified_projects"]) * 100)
        llm_output = PortfolioNarrativeLLMOutput(
            eligible=True,
            narrative=(
                f"{facts['tested_projects']} of {facts['total_verified_projects']} verified projects "
                f"have automated tests ({tested_pct}%)."
            ),
            testing_pattern=f"{tested_pct}% test coverage across verified projects.",
            collaboration_pattern=f"Collaboration modes: {facts['collaboration_distribution']}.",
            specialization="Narrative generation is temporarily unavailable.",
            biggest_weakness="Narrative generation is temporarily unavailable.",
        )
        degraded = True

    report = PortfolioNarrativeReport(
        **llm_output.model_dump(),
        generated_at=datetime.now(timezone.utc).isoformat(),
        analysis_degraded=degraded,
    )
    await _persist_portfolio_narrative(db, user_id, report)
    return report