import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import client, MODEL
from app.models.facts import Experience, Project, Resume
from app.models.inference import ResumeReview
from app.prompts.resume_review import RESUME_REVIEW_SYSTEM_PROMPT
from app.schemas.resume_review import (
    ATSFlag,
    BulletIssue,
    BulletReview,
    LLMReviewOutput,
    ResumeReviewReport,
    ResumeReviewStats,
)
from app.services.resume.ats_checks import run_ats_checks
from app.services.resume.bullet_analysis import analyze_bullet


class ReviewGenerationError(Exception):
    """Raised when the narrative/rewrite LLM call fails or returns
    something we can't validate. Same graceful-degradation pattern as
    InterpretationError in jobs/interpretation.py — callers fall back to
    a deterministic template instead of crashing the whole report.
    """


SEVERITY_PENALTY = {"high": 8, "medium": 4, "low": 2}


async def _get_latest_resume(db: AsyncSession, user_id) -> Resume | None:
    result = await db.execute(
        select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


def _build_review_units(experiences: list[Experience], projects: list[Project]) -> list[dict]:
    """Every Experience bullet is already a discrete unit. Project
    descriptions are one text blob (see extraction.py's prompt), so we
    split on newlines to get bullet-like units for the same treatment —
    this avoids any change to the Project/Experience schema itself.
    """
    units: list[dict] = []

    for exp in experiences:
        label = f"{exp.role} at {exp.company}"
        for i, bullet in enumerate(exp.bullets or []):
            if not bullet.strip():
                continue
            units.append({
                "bullet_id": f"exp_{exp.id}_{i}",
                "source_type": "experience",
                "source_id": str(exp.id),
                "source_label": label,
                "text": bullet,
                "context_stack": exp.stack or [],
            })

    for proj in projects:
        lines = [l.strip("-•* \t") for l in (proj.description or "").split("\n") if l.strip()]
        for i, line in enumerate(lines):
            units.append({
                "bullet_id": f"proj_{proj.id}_{i}",
                "source_type": "project",
                "source_id": str(proj.id),
                "source_label": proj.name,
                "text": line,
                "context_stack": proj.stack or [],
            })

    return units


def _compute_score(flagged_count: int, unit_count: int, ats_flags: list[dict]) -> float:
    if unit_count == 0:
        return 0.0
    ats_penalty = sum(SEVERITY_PENALTY.get(f["severity"], 2) for f in ats_flags)
    bullet_penalty = (flagged_count / unit_count) * 40
    score = 100 - ats_penalty - bullet_penalty
    return round(max(0.0, min(100.0, score)), 1)


async def _call_review_llm(context: dict) -> LLMReviewOutput:
    print(
        f"[TRACING] Requesting resume review narrative for "
        f"{len(context['flagged_bullets'])} flagged bullets...", flush=True
    )
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": RESUME_REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw resume review JSON:\n{content}", flush=True)
        return LLMReviewOutput.model_validate(json.loads(content))
    except Exception as e:
        raise ReviewGenerationError(f"Resume review LLM call failed: {e}") from e


def _fallback_review(context: dict) -> LLMReviewOutput:
    """Deterministic fallback, same idea as jobs/interpretation.py's
    fallback_narrative — every field still grounded in real facts, just
    without LLM-polished prose or rewrites.
    """
    flagged = context["flagged_bullets"]
    top_fixes = [
        f"Bullet '{b['bullet_id']}' ({b['source_label']}): {b['issues'][0]['detail']}"
        for b in flagged[:4]
    ]
    return LLMReviewOutput(
        summary=(
            f"{len(flagged)} of {context['total_bullets']} bullets were flagged for missing metrics, "
            f"weak openers, or passive voice. Automated rewrite suggestions are unavailable right now — "
            f"review the flagged bullets below manually."
        ),
        strengths=[],
        top_priority_fixes=top_fixes,
        rewrites=[],
    )


async def generate_resume_review(db: AsyncSession, user_id) -> ResumeReviewReport:
    resume = await _get_latest_resume(db, user_id)
    if resume is None:
        raise ValueError(
            "No uploaded resume found for this user — upload a resume via /resume/upload first."
        )

    exp_result = await db.execute(select(Experience).where(Experience.user_id == user_id))
    experiences = list(exp_result.scalars().all())

    proj_result = await db.execute(select(Project).where(Project.user_id == user_id))
    projects = list(proj_result.scalars().all())

    units = _build_review_units(experiences, projects)
    ats_flags = run_ats_checks(resume.raw_text)

    bullet_reviews: list[BulletReview] = []
    flagged_for_llm: list[dict] = []
    missing_metric_count = weak_verb_count = passive_voice_count = 0

    for unit in units:
        issues = analyze_bullet(unit["text"])
        for issue in issues:
            if issue["type"] == "missing_metric":
                missing_metric_count += 1
            elif issue["type"] == "weak_verb":
                weak_verb_count += 1
            elif issue["type"] == "passive_voice":
                passive_voice_count += 1

        bullet_reviews.append(BulletReview(
            bullet_id=unit["bullet_id"],
            source_type=unit["source_type"],
            source_id=unit["source_id"],
            source_label=unit["source_label"],
            original=unit["text"],
            issues=[BulletIssue(**i) for i in issues],
        ))

        if issues:
            flagged_for_llm.append({
                "bullet_id": unit["bullet_id"],
                "source_label": unit["source_label"],
                "context_stack": unit["context_stack"],
                "text": unit["text"],
                "issues": issues,
            })

    context = {
        "total_bullets": len(units),
        "flagged_bullets": flagged_for_llm,
        "ats_flags": ats_flags,
    }

    degraded = False
    if flagged_for_llm:
        try:
            llm_output = await _call_review_llm(context)
        except ReviewGenerationError as e:
            print(f"[TRACING] Resume review degraded, using fallback: {e}", flush=True)
            llm_output = _fallback_review(context)
            degraded = True
    else:
        llm_output = LLMReviewOutput(
            summary="No bullet-level issues were detected — nice work. Review the ATS flags below.",
            strengths=[], top_priority_fixes=[], rewrites=[],
        )

    # Merge LLM rewrites back onto the deterministic bullet list — never
    # trust the LLM's bullet_id list blindly (same rule as gap_analysis.py).
    rewrite_by_id = {r.bullet_id: r for r in llm_output.rewrites}
    for br in bullet_reviews:
        match = rewrite_by_id.get(br.bullet_id)
        if match:
            br.rewrite = match.rewrite
            br.rewrite_rationale = match.rationale

    score = _compute_score(len(flagged_for_llm), len(units), ats_flags)

    stats = ResumeReviewStats(
        total_bullets=len(units),
        flagged_bullets=len(flagged_for_llm),
        missing_metric_count=missing_metric_count,
        weak_verb_count=weak_verb_count,
        passive_voice_count=passive_voice_count,
    )

    report = ResumeReviewReport(
        overall_score=score,
        summary=llm_output.summary,
        strengths=llm_output.strengths,
        top_priority_fixes=llm_output.top_priority_fixes,
        bullet_reviews=bullet_reviews,
        ats_flags=[ATSFlag(**f) for f in ats_flags],
        stats=stats,
        analysis_degraded=degraded,
    )

    # Persist as an inference row only — Experience/Project rows are
    # never written to here (Phase 5's "no silent mutation" constraint).
    review_row = ResumeReview(
        user_id=user_id,
        resume_id=resume.id,
        review_json=report.model_dump(mode="json"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(review_row)
    await db.flush()
    await db.commit()

    return report