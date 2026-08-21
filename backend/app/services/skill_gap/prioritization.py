# backend/app/services/skill_gap/prioritization.py
import json
import logging

from app.core.llm import chat_completion, MODEL
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
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": PRIORITIZATION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        logger.debug("Raw prioritization JSON:\n%s", content)
        return PrioritizationResult.model_validate(json.loads(content))
    except Exception as e:
        raise PrioritizationError(f"Prioritization LLM call failed: {e}") from e