"""Goal/JD-aware project ranking — replaces the old generic pairwise
"which project wins on 4 hardcoded axes" comparison with a ranking
across the ENTIRE portfolio, scored against the user's actual target
role (missing/have skills from their most recent Skill Gap Analysis)
when one exists. Deterministic ranking only; prose explanation lives in
the Project Intelligence agent, never here.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import JobDescription
from app.schemas.project_intelligence import GoalAwareRanking, PortfolioComparisonResponse
from app.schemas.projects import ComparisonMetric, ProjectComparison
from app.services.projects.overview import build_projects_overview
from app.services.projects.scoring import AI_SKILLS, BACKEND_SKILLS

BASE_WEIGHT = 1.0
JD_MATCH_WEIGHT = 2.0
CLAIM_RISK_PENALTY = 1.0
UNDERSOLD_BONUS = 0.5
COLLABORATION_BONUS = 0.5
# Previously computed by overview.py but never consumed by any ranking or
# recommendation logic in this module. A "resume_it" project (stale but
# still high-quality) is worth surfacing before it's forgotten entirely;
# a "retire_it" project (stale AND low-quality) shouldn't be led with.
ABANDONMENT_RESUME_IT_BONUS = 0.5
ABANDONMENT_RETIRE_IT_PENALTY = 0.5

# Claim-risk severity used both for the ranking penalty above and for the
# reconciled pairwise "Lower claim-audit risk" metric below, so the two
# views of the same portfolio agree with each other instead of the
# pairwise card computing risk from a totally separate calculation.
_CLAIM_RISK_SEVERITY = {"high": 2, "medium": 1, "undersold": -1, None: 0}


async def _latest_missing_skills(db: AsyncSession, user_id, job_description_id=None) -> set[str]:
    stmt = (
        select(JobDescription)
        .where(JobDescription.user_id == user_id)
        .where(JobDescription.analysis_result.isnot(None))
    )
    if job_description_id is not None:
        stmt = stmt.where(JobDescription.id == job_description_id)
    stmt = stmt.order_by(JobDescription.created_at.desc()).limit(1)
    result = await db.execute(stmt)
    jd = result.scalar_one_or_none()
    if jd is None or not isinstance(jd.analysis_result, dict):
        return set()
    missing = jd.analysis_result.get("report", {}).get("missing", [])
    return {m.get("skill") for m in missing if m.get("skill")}


def _winner(a_name: str, b_name: str, a_value: float, b_value: float) -> str:
    if a_value == b_value:
        return "Tie"
    return a_name if a_value > b_value else b_name


async def build_goal_aware_ranking(db: AsyncSession, user_id, job_description_id=None, overview=None) -> PortfolioComparisonResponse:
    overview = overview or await build_projects_overview(db, user_id)
    if not overview.projects:
        return PortfolioComparisonResponse(ranked=[], lead_project=None, recommendation="")

    missing_skills = await _latest_missing_skills(db, user_id, job_description_id)
    missing_lower = {s.lower() for s in missing_skills}

    ranked_items: list[GoalAwareRanking] = []
    for p in overview.projects:
        stack_lower = {s.lower() for s in p.stack}
        reasons: list[str] = []
        score = BASE_WEIGHT * p.rating

        if missing_skills:
            # Reward overlap with the target job's requirements that this
            # project ALREADY demonstrates (i.e. not itself a gap).
            demonstrated_relevant = stack_lower - missing_lower
            if demonstrated_relevant:
                score += JD_MATCH_WEIGHT
                reasons.append("Demonstrates skills relevant to your most recent target job")

        if p.claim_risk in ("high", "medium"):
            score -= CLAIM_RISK_PENALTY
            reasons.append("Has unresolved claim-vs-implementation risk — resolve before leading with this one")
        elif p.claim_risk == "undersold":
            score += UNDERSOLD_BONUS
            reasons.append("Undersold — real verified depth not yet reflected in its resume description")

        if p.collaboration_mode in ("collaborative", "mixed"):
            score += COLLABORATION_BONUS
            reasons.append("Shows real PR/review collaboration, not just solo commits")

        if p.abandonment_status == "resume_it":
            score += ABANDONMENT_RESUME_IT_BONUS
            reasons.append("High-quality but stale — worth resuming and re-surfacing before it's forgotten")
        elif p.abandonment_status == "retire_it":
            score -= ABANDONMENT_RETIRE_IT_PENALTY
            reasons.append("Stale and low-quality — a weaker choice to lead with right now")

        if not reasons:
            reasons.append("Ranked by overall project rating")

        ranked_items.append(GoalAwareRanking(
            project_id=p.id, project_name=p.name, score=round(score, 2), reasons=reasons,
        ))

    ranked_items.sort(key=lambda r: r.score, reverse=True)
    lead = ranked_items[0].project_name if ranked_items else None
    recommendation = (
        f"Lead with {lead} for this application — {ranked_items[0].reasons[0].lower()}."
        if ranked_items else ""
    )

    return PortfolioComparisonResponse(ranked=ranked_items, lead_project=lead, recommendation=recommendation)


async def build_projects_comparison(db: AsyncSession, user_id, overview=None) -> ProjectComparison | None:
    """Kept for the existing pairwise-metrics UI card — now sourced from
    the top 2 of the goal-aware ranking instead of a generic rating
    sort, so the "winner" reflects real target-role relevance whenever
    a target job exists. The metric axes below now include one directly
    tied to a real ranking input (claim-audit risk) rather than being
    computed entirely independently of what the ranking score is actually
    based on — previously a project could win the overall ranking while
    losing every displayed axis, with nothing explaining why.
    """
    overview = overview or await build_projects_overview(db, user_id)
    ranking = await build_goal_aware_ranking(db, user_id, overview=overview)
    if len(ranking.ranked) < 2:
        return None
    by_id = {p.id: p for p in overview.projects}
    a = by_id[ranking.ranked[0].project_id]
    b = by_id[ranking.ranked[1].project_id]

    a_stack = {s.lower() for s in a.stack}
    b_stack = {s.lower() for s in b.stack}

    complexity_winner = _winner(a.name, b.name, len(a.stack) + len(a.capabilities), len(b.stack) + len(b.capabilities))
    ai_winner = _winner(a.name, b.name, len(a_stack & AI_SKILLS), len(b_stack & AI_SKILLS))
    backend_winner = _winner(a.name, b.name, len(a_stack & BACKEND_SKILLS), len(b_stack & BACKEND_SKILLS))
    goal_winner = _winner(a.name, b.name, ranking.ranked[0].score, ranking.ranked[1].score)

    a_risk = _CLAIM_RISK_SEVERITY.get(a.claim_risk, 0)
    b_risk = _CLAIM_RISK_SEVERITY.get(b.claim_risk, 0)
    claim_risk_winner = _winner(a.name, b.name, -a_risk, -b_risk)  # lower severity wins

    metrics = [
        ComparisonMetric(label="More complex", winner=complexity_winner),
        ComparisonMetric(label="Deeper AI", winner=ai_winner),
        ComparisonMetric(label="Stronger backend", winner=backend_winner),
        ComparisonMetric(label="Lower claim-audit risk", winner=claim_risk_winner),
        ComparisonMetric(label="Best fit for your target role", winner=goal_winner),
    ]

    return ProjectComparison(
        project_a=a.name, project_b=b.name, metrics=metrics, recommendation=ranking.recommendation,
    )