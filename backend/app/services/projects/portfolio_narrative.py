"""Portfolio-wide narrative review — engineering self-knowledge-facing.

Audience: the candidate wanting to understand their own engineering
patterns across verified projects (testing consistency, collaboration
mode, specialization, biggest weakness).

Distinct from GithubPortfolioReview (github/github_reviewer.py), which
takes a hiring-manager angle (role fit, recruiter impression, resume
integration) over the condensed github_knowledge object. This module is
now DELIBERATELY differentiated at the data level, not just the framing
level: it reads raw GithubProjectAnalysis rows directly (for the same
testing/collaboration/hygiene/architecture facts github_reviewer also
sees), AND it additionally reasons over resume-linkage coverage and
claim-audit risk distribution — facts that only exist inside the
Projects module and are never passed to github_reviewer.py's LLM call at
all. That's what makes the two surfaces genuinely different reads rather
than the same numbers narrated twice.
"""
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.facts import Project
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import PortfolioNarrativeReview, ProjectClaimAuditReview
from app.prompts.portfolio_narrative import PORTFOLIO_NARRATIVE_SYSTEM_PROMPT
from app.schemas.project_intelligence import PortfolioNarrativeLLMOutput, PortfolioNarrativeReport
from app.services.projects.linking import normalize_name

logger = logging.getLogger(__name__)

MIN_VERIFIED_PROJECTS_FOR_NARRATIVE = 2


async def _build_portfolio_facts(db: AsyncSession, user_id) -> dict | None:
    result = await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)
    )
    all_analyses = list(result.scalars().all())

    # Same fork-eligibility rule used everywhere else in this codebase
    # (overview.py, claim_audit.py's caller, recommendations.py,
    # github_knowledge.py, interview/context_builder.py) — a meaningfully-
    # contributed fork IS real evidence and should count here too.
    # Previously this filtered with `.where(GithubProjectAnalysis.is_fork.is_(False))`,
    # which excluded ALL forks including meaningfully-contributed ones,
    # producing a different repo count here than in GithubPortfolioReview
    # for the same user — a silent, user-visible inconsistency between
    # two surfaces describing the same portfolio.
    analyses = [
        a for a in all_analyses
        if not (a.is_fork and not a.is_meaningful_fork_contribution)
    ]
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

    # --- Projects-module-only facts, never visible to github_reviewer.py ---
    proj_result = await db.execute(select(Project).where(Project.user_id == user_id))
    all_projects = list(proj_result.scalars().all())
    seen_names: set[str] = set()
    projects: list[Project] = []
    for p in all_projects:
        norm = normalize_name(p.name)
        if norm not in seen_names:
            seen_names.add(norm)
            projects.append(p)

    resume_linked = sum(1 for p in projects if p.resume_id is not None)
    resume_linked_pct = round((resume_linked / len(projects)) * 100) if projects else None

    claim_risk_distribution = {"high": 0, "medium": 0, "low": 0}
    project_ids = [p.id for p in projects]
    if project_ids:
        audit_result = await db.execute(
            select(ProjectClaimAuditReview).where(ProjectClaimAuditReview.project_id.in_(project_ids))
        )
        for row in audit_result.scalars().all():
            level = ((row.report_json or {}).get("narrative", {})).get("risk_level", "low")
            if level not in claim_risk_distribution:
                level = "low"
            claim_risk_distribution[level] += 1

    return {
        "total_verified_projects": total,
        "tested_projects": tested,
        "ci_projects": ci,
        "collaboration_distribution": collab_counts,
        "average_commit_hygiene": avg_hygiene,
        "technology_distribution": dict(sorted(tech_counts.items(), key=lambda kv: kv[1], reverse=True)[:15]),
        "architecture_depth_distribution": depth_counts,
        # Unique to this module — real signal about the gap between what a
        # candidate BUILT (GitHub) and what they SHOW (resume), plus how
        # many of their own claims about their own work hold up under audit.
        "total_resume_projects": len(projects),
        "resume_linked_pct": resume_linked_pct,
        "claim_audit_risk_distribution": claim_risk_distribution,
        "claim_audits_run": sum(claim_risk_distribution.values()),
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
        logger.info("Requesting portfolio-wide narrative from LLM...")
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
        logger.debug("Raw portfolio narrative JSON: %s", content)
        llm_output = PortfolioNarrativeLLMOutput.model_validate(json.loads(content))
    except Exception as e:
        logger.warning("Portfolio narrative degraded, using fallback: %s", e)
        tested_pct = round((facts["tested_projects"] / facts["total_verified_projects"]) * 100)
        fallback_parts = [
            f"{facts['tested_projects']} of {facts['total_verified_projects']} verified projects "
            f"have automated tests ({tested_pct}%)."
        ]
        if facts.get("resume_linked_pct") is not None:
            fallback_parts.append(f"{facts['resume_linked_pct']}% of your projects are resume-linked.")
        llm_output = PortfolioNarrativeLLMOutput(
            eligible=True,
            narrative=" ".join(fallback_parts),
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