# backend/app/services/skill_gap/prioritization.py
import logging

from app.core.llm import Prompt, llm_json
from app.prompts.skill_gap.prioritization import PRIORITIZATION_SYSTEM_PROMPT
from app.schemas.skill_gap.prioritization import PrioritizationResult

logger = logging.getLogger(__name__)


class PrioritizationError(Exception):
    """Raised when the user-adjustment LLM call fails or returns
    something we can't trust. Callers fall back to the deterministic
    role_priority_order + a flat-rate estimate — same graceful-
    degradation pattern used throughout this codebase.
    """


async def prioritize_missing_skills(context: dict) -> PrioritizationResult:
    logger.debug(
        "Requesting prioritization adjustment for %d missing skills...",
        len(context.get("missing", [])),
    )
    try:
        reply = await llm_json(
            Prompt(PRIORITIZATION_SYSTEM_PROMPT, context), PrioritizationResult,
            label="skill_gap_prioritization", expect=("priority_order", "estimated_weeks"),
        )
    except Exception as e:
        raise PrioritizationError(f"Prioritization LLM call failed: {e}") from e
    return reply.value