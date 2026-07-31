"""Deterministic, advisory-only timeline-plausibility check between a
user's resume-claimed experience dates and their GitHub repository
creation dates for the same skill. This is NOT proof of anything — a
skill can be genuinely learned and used without ever touching a public
repo, and a repo's creation date says nothing about when the underlying
skill was first acquired. It's a single, honest signal: "does the
earliest public GitHub evidence for this skill line up with, or badly
contradict, when the resume claims it was used" — surfaced as a note to
consider, never as an accusation, and never blocking anything.

Deterministic date-overlap math only. No LLM involved.
"""
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# If GitHub-evidenced work on a skill starts more than this many days
# AFTER a resume-claimed experience using that skill ENDED, it's worth a
# plain, non-judgmental note — not flagged as contradictory, just as
# something the candidate should be ready to explain if asked.
IMPLAUSIBLE_GAP_DAYS = 180


def _to_date(dt: datetime | date | None) -> date | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.date()
    return dt


def check_skill_timeline_plausibility(
    canonical_skill: str,
    experience_windows: list[tuple[date | None, date | None]],
    earliest_github_repo_created_at: date | None,
) -> dict | None:
    """Returns a plausibility note dict, or None if there's nothing
    worth flagging (no data to compare, or the dates are consistent).
    """
    if earliest_github_repo_created_at is None or not experience_windows:
        return None

    for start, end in experience_windows:
        if start is None:
            continue
        # A repo created well before the experience even started is
        # normal (learned the skill first, applied it at work later) —
        # nothing to flag. Only repos created suspiciously LATE relative
        # to a claimed usage window that has already closed get a note.
        reference_end = end or date.today()
        gap_days = (earliest_github_repo_created_at - reference_end).days
        if gap_days > IMPLAUSIBLE_GAP_DAYS:
            return {
                "skill": canonical_skill,
                "type": "github_evidence_postdates_experience",
                "detail": (
                    f"Your earliest GitHub evidence for {canonical_skill.title()} is dated "
                    f"{earliest_github_repo_created_at.isoformat()}, which is {gap_days} days "
                    f"after the experience claiming to use it ended ({reference_end.isoformat()}). "
                    f"This isn't necessarily wrong — you may have used "
                    f"{canonical_skill.title()} without a public repo at the time — but be ready "
                    f"to explain the timeline if asked."
                ),
            }
    return None


async def build_timeline_plausibility_notes(db: AsyncSession, user_id, resume_id) -> list[dict]:
    """Runs the check for every skill that has BOTH resume-experience
    evidence with real dates AND GitHub repo evidence, using the
    earliest repo_created_at among eligible (non-thin-fork) repos
    evidencing that skill.
    """
    from app.models.facts import Experience
    from app.models.github_analysis import GithubProjectAnalysis
    from app.services.resume.skill_classifier import resolve_skills

    exp_result = await db.execute(
        select(Experience).where(Experience.user_id == user_id, Experience.resume_id == resume_id)
    )
    experiences = list(exp_result.scalars().all())
    if not experiences:
        return []

    gh_result = await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)
    )
    eligible_repos = [
        r for r in gh_result.scalars().all()
        if not (r.is_fork and not r.is_meaningful_fork_contribution) and r.repo_created_at is not None
    ]
    if not eligible_repos:
        return []

    earliest_repo_date_by_tech: dict[str, date] = {}
    for r in eligible_repos:
        repo_date = _to_date(r.repo_created_at)
        for tech in (r.technologies or []):
            key = tech.lower()
            if key not in earliest_repo_date_by_tech or repo_date < earliest_repo_date_by_tech[key]:
                earliest_repo_date_by_tech[key] = repo_date

    if not earliest_repo_date_by_tech:
        return []

    windows_by_canonical: dict[str, list[tuple[date | None, date | None]]] = {}
    all_raw: set[str] = set()
    for exp in experiences:
        all_raw.update(exp.stack or [])
    resolved = await resolve_skills(all_raw, db) if all_raw else {}

    for exp in experiences:
        window = (_to_date(exp.start_date), _to_date(exp.end_date))
        for raw in (exp.stack or []):
            canonical = resolved.get(raw)
            if canonical is None:
                continue
            windows_by_canonical.setdefault(canonical, []).append(window)

    notes: list[dict] = []
    for canonical, windows in windows_by_canonical.items():
        earliest_repo_date = earliest_repo_date_by_tech.get(canonical)
        note = check_skill_timeline_plausibility(canonical, windows, earliest_repo_date)
        if note:
            notes.append(note)

    return notes