# backend/app/api/jobs.py
"""Skill-gap comparison for a job that has already been parsed by Job
Intelligence (see api/job_intelligence.py for creating and listing jobs).
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.models.job_intelligence import GapAnalysisResultRow
from app.schemas.skill_gap.interpretation import CategoryScore, NarrativeAnalysis, OverallMatch
from app.schemas.skill_gap.skill_gap_page import SkillGapForJobResponse
from app.services.company_intelligence.reader import get_company_intelligence_by_source_hash
from app.services.identity.identity_refresh import trigger_identity_refresh
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.job_intelligence.gap_results import get_latest_gap_result, is_current_gap_result
from app.services.skill_gap.category_breakdown import (
    compute_category_breakdown,
    compute_overall_match,
)
from app.services.skill_gap.comparison import analyze_skill_gap
from app.services.skill_gap.narrative import (
    InterpretationError,
    build_narrative_context,
    fallback_narrative,
    generate_narrative_analysis,
)
from app.services.target_profile.builder import build_target_profile

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


async def _get_or_build_gap_result_for_job_intelligence(
    db: AsyncSession,
    user: User,
    job_intelligence,
    company_intelligence,
    regenerate: bool,
) -> GapAnalysisResultRow:
    """Runs the Comparison Engine + narrative over an existing job
    profile. Reads back the latest stored result instead when it is still
    current and the caller didn't ask to regenerate. Never re-extracts the
    job description itself.
    """
    job_intelligence_uuid = UUID(job_intelligence.id)

    if not regenerate:
        cached = await get_latest_gap_result(db, user.id, job_intelligence_uuid)
        if cached is not None and await is_current_gap_result(db, user.id, cached):
            return cached

    target_profile = build_target_profile(job_intelligence, company_intelligence)

    report = await analyze_skill_gap(db, user.id, target_profile.job_intelligence)
    logger.debug(
        "Gap analysis (job_intelligence_id=%s) complete: %d have, %d partial, %d missing.",
        job_intelligence_uuid, len(report.have), len(report.partial), len(report.missing),
    )

    category_breakdown = compute_category_breakdown(report.have, report.partial, report.missing)
    overall_match = compute_overall_match(
        target_profile.job_intelligence.canonical_skills_map, report.have, report.partial, report.missing,
    )
    context = build_narrative_context(
        role=job_intelligence.role,
        company=job_intelligence.company,
        have=report.have,
        partial=report.partial,
        missing=report.missing,
        priority_order=report.priority_order,
        category_breakdown=category_breakdown,
        overall_match=overall_match,
        job_interview_focus_areas=target_profile.job_intelligence.interview_focus_areas,
    )

    degraded = False
    try:
        analysis = await generate_narrative_analysis(context)
    except InterpretationError as e:
        logger.warning("Narrative generation degraded, using fallback: %s", e)
        analysis = fallback_narrative(context)
        degraded = True

    gap_result_row = GapAnalysisResultRow(
        user_id=user.id,
        job_intelligence_id=job_intelligence_uuid,
        company_intelligence_id=(
            UUID(company_intelligence.id) if company_intelligence and company_intelligence.id else None
        ),
        report_json=report.model_dump(mode="json"),
        category_breakdown_json={"items": category_breakdown},
        overall_match_json=overall_match,
        narrative_json=analysis.model_dump(mode="json"),
        analysis_degraded=degraded,
        created_at=datetime.now(timezone.utc),
    )
    db.add(gap_result_row)
    await db.commit()
    await db.refresh(gap_result_row)

    await trigger_identity_refresh(db, user.id, "job description analysis")

    return gap_result_row


@router.get("/by-intelligence/{job_intelligence_id}", response_model=SkillGapForJobResponse)
async def get_skill_gap_for_job_intelligence(
    job_intelligence_id: UUID,
    regenerate: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare the current user's evidence against one of their parsed
    jobs (from GET /job-intelligence). Every met requirement carries the
    items that support it; every gap carries a severity.
    """
    job_intelligence = await get_job_intelligence(db, current_user.id, job_intelligence_id)
    if job_intelligence is None:
        raise HTTPException(status_code=404, detail="Job intelligence profile not found")

    company_intelligence = await get_company_intelligence_by_source_hash(
        db, current_user.id, job_intelligence.source_text_hash,
    )

    gap_row = await _get_or_build_gap_result_for_job_intelligence(
        db, current_user, job_intelligence, company_intelligence, regenerate,
    )

    return SkillGapForJobResponse(
        job_intelligence=job_intelligence,
        company_intelligence=company_intelligence,
        report=gap_row.report_json,
        category_breakdown=[CategoryScore(**c) for c in gap_row.category_breakdown_json.get("items", [])],
        overall_match=OverallMatch(**gap_row.overall_match_json),
        analysis=NarrativeAnalysis(**gap_row.narrative_json),
        analysis_degraded=gap_row.analysis_degraded,
        generated_at=gap_row.created_at.isoformat(),
    )
