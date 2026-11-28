"""How the tailored resume scores against the one the user uploaded: coverage of
the job's keywords, and the analysis engine's ATS checks.

Both are measured by the same rules, on the text a screening system would read.
Only wording that is on the resume counts, so a suggestion changes the score
once it is accepted. No model calls, and nothing is saved.
"""
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Education, Experience, Project, Resume
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.schemas.resume.tailored import TailoredResumeDocument
from app.schemas.resume.tailored_score import KeywordCoverage, ResumeScore, ScoreCard, UploadedResume
from app.services.resume.analysis.ats_scorer_v2 import analyze_ats_v2
from app.services.resume.analysis.keywords import analyze_keywords, job_keywords
from app.services.resume.render import plain_text

def _score(text: str, keywords: set[str], experiences, projects, education, skills=None) -> ScoreCard:
    ats = analyze_ats_v2(
        raw_text=text, experiences=experiences, projects=projects, education=education, profile_skills=skills,
    )
    coverage = None
    if keywords:  # without any, the analyzer would measure a general list instead
        found = analyze_keywords(text, keywords)
        coverage = KeywordCoverage(
            matched=found["matched"], missing=sorted(keywords - set(found["matched"])),
            total=found["total_keywords"], percentage=found["coverage_pct"],
        )
    return ScoreCard(
        ats_score=ats["score"], parts=ats["module_scores"], warnings=ats["warnings"], keywords=coverage,
    )


def score_document(document: TailoredResumeDocument, keywords: set[str], text: str | None = None) -> ScoreCard:
    """The tailored resume's score; `text` is its wording as read back from an
    exported file, to score that instead.
    """
    # The checks read the shape of stored rows, so the document is given that shape.
    experiences = [
        SimpleNamespace(
            id=index, bullets=[line.text for line in e.bullets], stack=[],
            start_date=e.start_date, end_date=e.end_date,
        )
        for index, e in enumerate(document.experience)
    ]
    projects = [
        # No creation date: projects are listed by relevance, which isn't a fault.
        SimpleNamespace(
            description="\n".join(line.text for line in p.bullets), stack=p.technologies, created_at=None,
        )
        for p in document.projects
    ]
    return _score(
        plain_text(document) if text is None else text, keywords, experiences, projects, document.education,
        {skill.name for skill in document.skills} or None,
    )


async def score_resume(
    db: AsyncSession, user_id, job: JobIntelligenceProfile, document: TailoredResumeDocument,
) -> ResumeScore:
    """The tailored resume's score, and the latest uploaded resume's for the
    same job. `before` is None when the user has uploaded none.
    """
    keywords = job_keywords(job)
    result = ResumeScore(after=score_document(document, keywords))

    upload = await db.scalar(
        select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(1)
    )
    if upload is None:
        return result

    async def rows(model) -> list:
        query = select(model).where(model.user_id == user_id, model.resume_id == upload.id)
        return list((await db.scalars(query.order_by(model.created_at))).all())

    result.before = _score(
        upload.raw_text or "", keywords, await rows(Experience), await rows(Project), await rows(Education),
    )
    result.uploaded = UploadedResume(filename=upload.filename, uploaded_at=upload.created_at)
    return result
