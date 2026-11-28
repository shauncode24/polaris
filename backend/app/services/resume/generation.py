"""Builds the resume tailored to one job: chooses the evidence, then asks for
rewrites of its bullets.

The choosing needs no model and already produces a complete resume, in the
evidence's own wording with the bullets most relevant to the job first. That
is what the user gets when the model fails, with a notice saying so; rewrites
made before the failure are kept.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.resume.tailored import Selection, TailoredResumeDocument
from app.services.resume.rewriting import rewrite_bullets
from app.services.resume.selection import select_for_job

_NOTHING_REWORDED = (
    "No bullets were reworded. This resume uses your own wording, with the bullets most relevant to the job first."
)
_SOME_REWORDED = "Only some bullets have a suggested rewording. The others keep your own wording."


def _notice(document: TailoredResumeDocument, problem: str) -> str:
    reworded = any(line.rewrite for line in document.lines())
    return f"{_SOME_REWORDED if reworded else _NOTHING_REWORDED} {problem}"


async def generate_tailored_resume(db: AsyncSession, user_id, job_intelligence_id) -> Selection | None:
    """The resume for this job and how the evidence ranked; not saved. None
    when the user has no such job. A model failure is never raised: the
    document's `notice` says what it cost.
    """
    selection = await select_for_job(db, user_id, job_intelligence_id)
    if selection is None:
        return None
    result = await rewrite_bullets(db, user_id, job_intelligence_id, selection.document)
    if result is None:  # the job was deleted meanwhile
        return None
    if result.problem:
        result.document.notice = _notice(result.document, result.problem)
    return Selection(document=result.document, ranking=selection.ranking)
