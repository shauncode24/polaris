"""Resume Analysis Engine — Orchestrator.

Runs all 7 analysis modules against the user's latest resume,
aggregates the scores, generates suggestions, and persists the result
as a ResumeAnalysis row.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Experience, Project, JobDescription, Resume
from app.models.inference import ResumeAnalysis

from app.services.resume.analysis.structure   import analyze_structure
from app.services.resume.analysis.parsing     import analyze_parsing
from app.services.resume.analysis.formatting  import analyze_formatting
from app.services.resume.analysis.content     import analyze_content
from app.services.resume.analysis.metrics     import analyze_metrics
from app.services.resume.analysis.keywords    import analyze_keywords
from app.services.resume.analysis.evidence    import analyze_evidence
from app.services.resume.analysis.scoring     import compute_overall_score, get_grade, get_label, get_grade_color
from app.services.resume.analysis.suggestions import generate_suggestions


def _collect_bullets(experiences: list, projects: list) -> list[str]:
    bullets: list[str] = []
    for exp in experiences:
        for b in (exp.bullets or []):
            stripped = b.strip()
            if stripped:
                bullets.append(stripped)
    for proj in projects:
        if proj.description:
            for line in proj.description.split("\n"):
                stripped = line.strip("-•*▪ \t")
                if len(stripped) > 10:
                    bullets.append(stripped)
    return bullets


async def run_analysis(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_description_id: uuid.UUID | str | None = None,
) -> dict:
    """Run the full deterministic analysis pipeline and persist the result."""

    # ── 1. Fetch latest resume ───────────────────────────────────────────────
    resume_result = await db.execute(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    resume = resume_result.scalar_one_or_none()
    if not resume:
        raise ValueError("No resume found for user.")

    raw_text = resume.raw_text or ""

    # ── 2. Fetch experiences & projects tied to this resume ─────────────────
    exp_result = await db.execute(
        select(Experience).where(
            Experience.user_id == user_id,
            Experience.resume_id == resume.id,
        )
    )
    experiences = list(exp_result.scalars().all())

    proj_result = await db.execute(
        select(Project).where(
            Project.user_id == user_id,
            Project.resume_id == resume.id,
        )
    )
    projects = list(proj_result.scalars().all())

    all_bullets = _collect_bullets(experiences, projects)

    # ── 3. JD keyword extraction (if provided) ───────────────────────────────
    jd_keywords: set[str] | None = None
    if job_description_id:
        jd_id = uuid.UUID(str(job_description_id))
        jd_result = await db.execute(
            select(JobDescription).where(
                JobDescription.id == jd_id,
                JobDescription.user_id == user_id,
            )
        )
        jd = jd_result.scalar_one_or_none()
        if jd and jd.extracted_requirements:
            skills = jd.extracted_requirements.get("skills", [])
            if skills:
                jd_keywords = {s.lower() for s in skills if s}

    # ── 4. Run all modules ───────────────────────────────────────────────────
    structure  = analyze_structure(raw_text)
    parsing    = analyze_parsing(raw_text)
    formatting = analyze_formatting(raw_text)
    content    = analyze_content(all_bullets)
    metrics    = analyze_metrics(all_bullets)
    keywords   = analyze_keywords(raw_text, jd_keywords)
    evidence   = await analyze_evidence(db, user_id, resume.id)

    # ── 5. Aggregate ─────────────────────────────────────────────────────────
    module_scores = {
        "structure":  structure["score"],
        "parsing":    parsing["score"],
        "formatting": formatting["score"],
        "content":    content["score"],
        "metrics":    metrics["score"],
        "keywords":   keywords["score"],
        "evidence":   evidence["score"],
    }

    overall    = compute_overall_score(module_scores)
    grade      = get_grade(overall)
    label      = get_label(overall)
    grade_color = get_grade_color(overall)

    # ── 6. Suggestions ───────────────────────────────────────────────────────
    suggestions = generate_suggestions(
        structure, parsing, formatting, content, metrics, keywords, evidence
    )

    report: dict = {
        "overall_score":  overall,
        "grade":          grade,
        "label":          label,
        "grade_color":    grade_color,
        "module_scores":  module_scores,
        "modules": {
            "structure":  structure,
            "parsing":    parsing,
            "formatting": formatting,
            "content":    content,
            "metrics":    metrics,
            "keywords":   keywords,
            "evidence":   evidence,
        },
        "suggestions": suggestions,
        "resume_id":   str(resume.id),
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }

    # ── 7. Persist ───────────────────────────────────────────────────────────
    row = ResumeAnalysis(
        user_id=user_id,
        resume_id=resume.id,
        analysis_json=report,
    )
    db.add(row)
    await db.flush()
    await db.commit()

    return report
