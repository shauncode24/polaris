"""The interview kit as its page shows it: each question with the evidence matched
to it, the answer outline and how practice has gone. No model calls.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.interview.kit_view import KitDetail, KitJob, KitPage, QuestionView
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.services.evidence.confidence import get_hidden_skill_names
from app.services.interview.kit_answers import answer_outlines
from app.services.interview.kit_store import get_kit, list_versions
from app.services.interview.practice import kit_progress
from app.services.job_intelligence.builder import get_job_intelligence


def _shows(question, outline, job_names: dict[str, str], hidden: set[str]) -> list[str]:
    """The matched evidence's skills (as the job writes them) and competencies.
    Nothing when the outline has no story: the match no longer holds.
    """
    if outline.story is None or not question.evidence_refs:
        return []
    ref = question.evidence_refs[0]
    skills = [job_names.get(s, s.replace("_", " ")) for s in ref.get("skills", []) if s not in hidden]
    return skills + [c.replace("_", " ") for c in ref.get("competencies", [])]


def _job_names(job: JobIntelligenceProfile) -> dict[str, str]:
    names: dict[str, str] = {}
    for skill in [*job.enriched_required_skills, *job.enriched_implicit_skills, *job.enriched_nice_to_have]:
        names.setdefault(skill.canonical, skill.raw)
    return names


async def kit_page(db: AsyncSession, user_id, job_intelligence_id, version: int | None = None) -> KitPage | None:
    """The user's kit for this job: the newest version unless one is named. None
    when the job isn't theirs or the named version doesn't exist.
    """
    job = await get_job_intelligence(db, user_id, job_intelligence_id)
    if job is None:
        return None
    saved = await get_kit(db, user_id, job_intelligence_id, version)
    if saved is None and version is not None:
        return None
    page = KitPage(
        job=KitJob(id=str(job_intelligence_id), role=job.role, company=job.company),
        versions=await list_versions(db, user_id, job_intelligence_id),
    )
    if saved is None:
        return page

    # The version just read, so a kit generated meanwhile can't mix in.
    number = saved.kit.version
    outlines = await answer_outlines(db, user_id, job_intelligence_id, number)
    progress = await kit_progress(db, user_id, job_intelligence_id, number)
    outline_of = {o.question_id: o for o in outlines.outlines}
    progress_of = {q.question_id: q for q in progress.questions}
    names, hidden = _job_names(job), await get_hidden_skill_names(db, user_id)

    page.kit = KitDetail(
        version=number, created_at=saved.kit.created_at, notice=saved.kit.notice,
        evidence_notice=saved.kit.evidence_notice, stale=outlines.stale, total=progress.total,
        practised=progress.practised, weakest=progress.weakest, categories=progress.categories,
        questions=[
            QuestionView(
                id=str(q.id), category=q.category, topic=q.topic, text=q.text, origin=q.origin,
                thin=q.thin_evidence, shows=_shows(q, outline_of[q.id], names, hidden), outline=outline_of[q.id],
                attempts=progress_of[q.id].attempts, latest_score=progress_of[q.id].latest_score,
            )
            for q in saved.questions
        ],
    )
    return page
