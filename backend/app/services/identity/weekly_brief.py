import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.inference import EngineeringIdentity, WeeklyBrief
from app.prompts.identity.weekly_brief import WEEKLY_BRIEF_SYSTEM_PROMPT
from app.schemas.identity.engineering_identity import IdentityFacts
from app.schemas.identity.weekly_brief import SkillDelta, WeeklyBriefFacts, WeeklyBriefLLMOutput, WeeklyBriefReport

MIN_DAYS_BETWEEN_SNAPSHOTS = 6
SIGNIFICANT_CONFIDENCE_DELTA = 0.05


class WeeklyBriefError(Exception):
    """Raised when the weekly-brief narrative LLM call fails or returns
    something we can't validate. Same graceful-degradation pattern used
    throughout this codebase.
    """


class InsufficientHistoryError(Exception):
    """Raised when there isn't yet a second EngineeringIdentity snapshot
    old enough to diff against. Expected, non-error state for a new
    user — callers should surface this as 'check back next week', not
    as a failure.
    """


def _skill_map(facts: IdentityFacts) -> dict[str, float]:
    return {s.skill: s.confidence for s in facts.top_skills}


async def _get_latest_two_identities(
    db: AsyncSession, user_id
) -> tuple[EngineeringIdentity, EngineeringIdentity | None]:
    result = await db.execute(
        select(EngineeringIdentity)
        .where(EngineeringIdentity.user_id == user_id)
        .order_by(EngineeringIdentity.created_at.desc())
    )
    rows = list(result.scalars().all())
    if not rows:
        raise InsufficientHistoryError("No Engineering Identity has been generated yet.")

    current = rows[0]
    cutoff = current.created_at - timedelta(days=MIN_DAYS_BETWEEN_SNAPSHOTS)
    previous = next((r for r in rows[1:] if r.created_at <= cutoff), None)
    return current, previous


def _build_facts_diff(
    current: IdentityFacts,
    previous: IdentityFacts | None,
    current_created_at,
    previous_created_at,
) -> WeeklyBriefFacts:
    if previous is None:
        return WeeklyBriefFacts(previous_generated_at=None, current_generated_at=current_created_at)

    curr_skills = _skill_map(current)
    prev_skills = _skill_map(previous)

    strengthened: list[SkillDelta] = []
    weakened: list[SkillDelta] = []
    for skill in set(curr_skills) & set(prev_skills):
        delta = round(curr_skills[skill] - prev_skills[skill], 3)
        if delta >= SIGNIFICANT_CONFIDENCE_DELTA:
            strengthened.append(SkillDelta(
                skill=skill, previous_confidence=prev_skills[skill],
                current_confidence=curr_skills[skill], delta=delta,
            ))
        elif delta <= -SIGNIFICANT_CONFIDENCE_DELTA:
            weakened.append(SkillDelta(
                skill=skill, previous_confidence=prev_skills[skill],
                current_confidence=curr_skills[skill], delta=delta,
            ))
    strengthened.sort(key=lambda s: s.delta, reverse=True)
    weakened.sort(key=lambda s: s.delta)

    resume_score_delta = None
    if current.resume_score is not None and previous.resume_score is not None:
        resume_score_delta = round(current.resume_score - previous.resume_score, 1)

    curr_commits = current.github_summary.get("total_commits_last_30_days")
    prev_commits = previous.github_summary.get("total_commits_last_30_days")
    github_commits_delta = (
        (curr_commits - prev_commits) if (curr_commits is not None and prev_commits is not None) else None
    )

    curr_repos = current.github_summary.get("repos_synced") or 0
    prev_repos = previous.github_summary.get("repos_synced") or 0
    github_new_repos = max(0, curr_repos - prev_repos)

    # NEW — GitHub's own trend computation (github_insights.py::build_github_insights'
    # "progress" block), already real, already computed at sync time relative to the
    # PRIOR github sync. Previously this genuinely useful signal was invisible to the
    # weekly brief, which only ever computed a cruder commit-count-only diff itself.
    gh_progress = current.github_progress or {}
    doc_trend = gh_progress.get("documentation")
    test_trend = gh_progress.get("testing")
    new_techs = gh_progress.get("new_technologies", [])

    curr_solved = current.leetcode_summary.get("total_solved")
    prev_solved = previous.leetcode_summary.get("total_solved")
    leetcode_solved_delta = (
        (curr_solved - prev_solved) if (curr_solved is not None and prev_solved is not None) else None
    )

    goals_progress = [{"title": g["title"], "status_pct": g["status_pct"]} for g in current.active_goals]

    return WeeklyBriefFacts(
        previous_generated_at=previous_created_at,
        current_generated_at=current_created_at,
        skills_strengthened=strengthened,
        skills_weakened=weakened,
        resume_score_delta=resume_score_delta,
        github_commits_delta=github_commits_delta,
        github_new_repos=github_new_repos,
        github_documentation_trend=doc_trend if doc_trend not in (None, "Unchanged") else None,
        github_testing_trend=test_trend if test_trend not in (None, "Unchanged") else None,
        github_new_technologies=new_techs,
        leetcode_solved_delta=leetcode_solved_delta,
        goals_progress=goals_progress,
    )


def _fallback_narrative(facts: WeeklyBriefFacts) -> WeeklyBriefLLMOutput:
    changes = []
    if facts.skills_strengthened:
        top = facts.skills_strengthened[0]
        changes.append(f"{top.skill.title()} confidence rose by {round(top.delta * 100)} points.")
    if facts.skills_weakened:
        top = facts.skills_weakened[0]
        changes.append(f"{top.skill.title()} confidence dropped by {round(abs(top.delta) * 100)} points.")
    if facts.resume_score_delta:
        direction = "improved" if facts.resume_score_delta > 0 else "dropped"
        changes.append(f"Resume score {direction} by {abs(facts.resume_score_delta)} points.")
    if facts.github_commits_delta:
        changes.append(f"GitHub commit activity changed by {facts.github_commits_delta} commits over the last 30 days.")
    if facts.github_documentation_trend:
        changes.append(f"GitHub documentation trend: {facts.github_documentation_trend.lower()}.")
    if facts.github_testing_trend:
        changes.append(f"GitHub testing trend: {facts.github_testing_trend.lower()}.")
    if facts.github_new_technologies:
        changes.append(f"New technologies appeared in GitHub activity: {', '.join(facts.github_new_technologies[:3])}.")
    if facts.leetcode_solved_delta:
        changes.append(f"Solved {facts.leetcode_solved_delta} more LeetCode problems.")

    return WeeklyBriefLLMOutput(
        headline="Weekly update" if changes else "No significant changes this week",
        whats_changed=changes,
        biggest_leverage_move=(
            "Keep syncing GitHub and LeetCode regularly so this brief has real deltas to report."
            if not changes else ""
        ),
    )


async def generate_weekly_brief(db: AsyncSession, user_id) -> WeeklyBriefReport:
    current_row, previous_row = await _get_latest_two_identities(db, user_id)

    current_facts = IdentityFacts.model_validate(current_row.facts_json)
    previous_facts = IdentityFacts.model_validate(previous_row.facts_json) if previous_row else None

    facts = _build_facts_diff(
        current_facts, previous_facts,
        current_row.created_at, previous_row.created_at if previous_row else None,
    )

    degraded = False
    if previous_row is None:
        narrative = WeeklyBriefLLMOutput(
            headline="First snapshot recorded",
            whats_changed=[],
            biggest_leverage_move="Check back in about a week once there's a second snapshot to compare against.",
        )
    else:
        try:
            print("[TRACING] Requesting weekly brief narrative from LLM...", flush=True)
            response = await chat_completion(
                model=MODEL,
                messages=[
                    {"role": "system", "content": WEEKLY_BRIEF_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(facts.model_dump(mode="json"))},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            content = response.choices[0].message.content
            print(f"[TRACING] Raw weekly brief JSON:\n{content}", flush=True)
            narrative = WeeklyBriefLLMOutput.model_validate(json.loads(content))
        except Exception as e:
            print(f"[TRACING] Weekly brief narrative degraded, using fallback: {e}", flush=True)
            narrative = _fallback_narrative(facts)
            degraded = True

    report = WeeklyBriefReport(
        facts=facts, narrative=narrative,
        generated_at=datetime.now(timezone.utc), analysis_degraded=degraded,
    )

    row = WeeklyBrief(
        user_id=user_id,
        brief_json=report.model_dump(mode="json"),
        created_at=report.generated_at,
    )
    db.add(row)
    await db.flush()
    await db.commit()

    return report


async def get_latest_weekly_brief(db: AsyncSession, user_id) -> WeeklyBriefReport | None:
    result = await db.execute(
        select(WeeklyBrief)
        .where(WeeklyBrief.user_id == user_id)
        .order_by(WeeklyBrief.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return WeeklyBriefReport.model_validate(row.brief_json)