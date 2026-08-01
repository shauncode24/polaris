import json
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.facts import Experience, Project, Resume
from app.models.inference import ResumeReview
from app.prompts.resume_review import (
    RESUME_NARRATIVE_SYSTEM_PROMPT,
    RESUME_REWRITES_SYSTEM_PROMPT,
)
from app.schemas.resume_review import (
    ATSFlag,
    BulletIssue,
    BulletReview,
    LLMNarrativeOutput,
    LLMRewritesOutput,
    ResumeReviewReport,
    ResumeReviewStats,
    BulletRewriteSuggestion,
)
from app.services.resume.analysis.ats_scorer_v2 import analyze_ats_v2
from app.services.resume.bullet_analysis import analyze_bullet, build_bullet_units as _build_review_units
from app.services.resume.text_sanitize import sanitize_ai_text as sanitize_ai_review_text

from app.models.inference import ResumeAnalysis, ProjectClaimAuditReview

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





def _compute_score(flagged_count: int, unit_count: int, ats_flags: list[dict]) -> float:
    if unit_count == 0:
        return 0.0
    ats_penalty = sum(SEVERITY_PENALTY.get(f["severity"], 2) for f in ats_flags)
    bullet_penalty = (flagged_count / unit_count) * 40
    score = 100 - ats_penalty - bullet_penalty
    return round(max(0.0, min(100.0, score)), 1)


async def _call_narrative_llm(context: dict) -> LLMNarrativeOutput:
    print(
        f"[TRACING] Requesting resume review narrative...", flush=True
    )
    # We pass context containing the first 15 flagged bullets
    # plus the total count to keep the narrative prompt token count reasonable.
    light_context = {
        "total_bullets": context["total_bullets"],
        "flagged_bullets": context["flagged_bullets"][:15],
        "ats_flags": context["ats_flags"],
    }
    try:
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": RESUME_NARRATIVE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(light_context)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw resume narrative JSON:\n{content}", flush=True)
        return LLMNarrativeOutput.model_validate(json.loads(content))
    except Exception as e:
        raise ReviewGenerationError(f"Resume review narrative LLM call failed: {e}") from e


async def _call_rewrites_llm_batch(bullets_batch: list[dict]) -> list[BulletRewriteSuggestion]:
    print(
        f"[TRACING] Requesting resume bullet rewrites for {len(bullets_batch)} bullets...", flush=True
    )
    try:
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": RESUME_REWRITES_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(bullets_batch)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw resume rewrites batch JSON:\n{content}", flush=True)
        parsed = LLMRewritesOutput.model_validate(json.loads(content))
        return parsed.rewrites
    except Exception as e:
        raise ReviewGenerationError(f"Resume review rewrites LLM call failed: {e}") from e


async def _get_canonical_analysis(db: AsyncSession, resume_id) -> dict | None:
    """Single source of truth for both score AND ATS warnings — replaces
    the separate run_ats_checks() call below, which duplicated
    analyze_ats_v2()'s warnings with different logic and could disagree.
    """
    result = await db.execute(
        select(ResumeAnalysis)
        .where(ResumeAnalysis.resume_id == resume_id)
        .order_by(ResumeAnalysis.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None or not isinstance(row.analysis_json, dict):
        return None
    return row.analysis_json


async def generate_resume_review(db: AsyncSession, user_id) -> ResumeReviewReport:
    resume = await _get_latest_resume(db, user_id)
    if resume is None:
        raise ValueError(
            "No uploaded resume found for this user — upload a resume via /resume/upload first."
        )

    exp_result = await db.execute(
        select(Experience).where(Experience.user_id == user_id, Experience.resume_id == resume.id)
    )
    experiences = list(exp_result.scalars().all())

    proj_result = await db.execute(
        select(Project).where(Project.user_id == user_id, Project.resume_id == resume.id)
    )
    projects = list(proj_result.scalars().all())

    # NEW — education wasn't fetched before; analyze_ats_v2 needs it for
    # the same-vocabulary fallback below.
    from app.models.facts import Education
    edu_result = await db.execute(
        select(Education).where(Education.user_id == user_id, Education.resume_id == resume.id)
    )
    education = list(edu_result.scalars().all())

    # Surface any existing claim-audit risk findings for this resume's
    # projects — previously the Projects module and Resume Reviewer never
    # talked to each other despite reasoning about the same claims.
    claim_flags: list[str] = []
    if projects:
        audit_result = await db.execute(
            select(ProjectClaimAuditReview).where(
                ProjectClaimAuditReview.project_id.in_([p.id for p in projects])
            )
        )
        for row in audit_result.scalars().all():
            narrative_dict = (row.report_json or {}).get("narrative", {})
            if narrative_dict.get("risk_level") in ("high", "medium"):
                claim_flags.append(f"{narrative_dict.get('headline', 'Claim risk detected')} (project claim audit)")

    units = _build_review_units(experiences, projects)
    canonical_analysis = await _get_canonical_analysis(db, resume.id)

    # FIX (Important #3): previously fell back to the legacy, weaker
    # ats_checks.run_ats_checks() whenever no ResumeAnalysis row existed
    # yet — meaning the warnings/severities a user saw from /resume/review
    # literally depended on whether they'd already called /resume/analyze.
    # Now both paths always speak ats_scorer_v2's vocabulary.
    if canonical_analysis:
        ats_flags = canonical_analysis.get("warnings", [])
    else:
        ats_res = analyze_ats_v2(
            raw_text=resume.raw_text,
            experiences=experiences,
            projects=projects,
            education=education,
            profile_skills=None,
        )
        ats_flags = ats_res.get("warnings", [])

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
    narrative = None
    rewrites: list[BulletRewriteSuggestion] = []

    if flagged_for_llm:
        # 1. Generate Narrative
        try:
            narrative = await _call_narrative_llm(context)
        except ReviewGenerationError as e:
            print(f"[TRACING] Resume review narrative degraded, using fallback: {e}", flush=True)
            narrative = LLMNarrativeOutput(
                summary=(
                    f"{len(flagged_for_llm)} of {len(units)} bullets were flagged for missing metrics, "
                    f"weak openers, or passive voice. Narrative review is unavailable right now."
                ),
                strengths=[],
                top_priority_fixes=[
                    f"Bullet '{b['bullet_id']}' ({b['source_label']}): {b['issues'][0]['detail']}"
                    for b in flagged_for_llm[:4]
                ]
            )
            degraded = True

        # 2. Generate Rewrites in batches of 15
        batch_size = 15
        for i in range(0, len(flagged_for_llm), batch_size):
            batch = flagged_for_llm[i : i + batch_size]
            try:
                batch_rewrites = await _call_rewrites_llm_batch(batch)
                rewrites.extend(batch_rewrites)
            except ReviewGenerationError as e:
                print(f"[TRACING] Bullet rewrites batch failed: {e}", flush=True)
                degraded = True
                continue
    else:
        narrative = LLMNarrativeOutput(
            summary="No bullet-level issues were detected — nice work. Review the ATS flags below.",
            strengths=[],
            top_priority_fixes=[],
        )

    # Merge LLM rewrites back onto the deterministic bullet list — never
    # trust the LLM's bullet_id list blindly (same rule as gap_analysis.py).
    rewrite_by_id = {r.bullet_id: r for r in rewrites}
    for br in bullet_reviews:
        match = rewrite_by_id.get(br.bullet_id)
        if match:
            br.rewrite = match.rewrite
            br.rewrite_rationale = match.rationale

    canonical_score = canonical_analysis.get("overall_score") if canonical_analysis else None
    if canonical_score is None:
        canonical_score = _compute_score(len(flagged_for_llm), len(units), ats_flags)
    score = canonical_score

    stats = ResumeReviewStats(
        total_bullets=len(units),
        flagged_bullets=len(flagged_for_llm),
        missing_metric_count=missing_metric_count,
        weak_verb_count=weak_verb_count,
        passive_voice_count=passive_voice_count,
    )

    report = ResumeReviewReport(
        overall_score=score,
        summary=sanitize_ai_review_text(narrative.summary),
        strengths=[sanitize_ai_review_text(s) for s in narrative.strengths] if narrative.strengths else [],
        top_priority_fixes=(
            [sanitize_ai_review_text(f) for f in narrative.top_priority_fixes] if narrative.top_priority_fixes else []
        ) + claim_flags,
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