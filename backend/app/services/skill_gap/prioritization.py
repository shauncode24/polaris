# backend/app/services/skill_gap/prioritization.py
import json

from app.core.llm import chat_completion, MODEL
from app.prompts.skill_gap_prioritization import PRIORITIZATION_SYSTEM_PROMPT
from app.schemas.prioritization import PrioritizationResult


class PrioritizationError(Exception):
    """Raised when the user-adjustment LLM call fails or returns
    something we can't trust. Callers fall back to the deterministic
    role_priority_order + a flat-rate estimate — same graceful-
    degradation pattern used throughout this codebase.
    """


async def prioritize_missing_skills(context: dict) -> PrioritizationResult:
    print(
        f"[TRACING] Requesting user-specific prioritization adjustment for "
        f"{len(context.get('missing', []))} missing skills...", flush=True,
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
        print(f"[TRACING] Raw prioritization JSON:\n{content}", flush=True)
        return PrioritizationResult.model_validate(json.loads(content))
    except Exception as e:
        raise PrioritizationError(f"Prioritization LLM call failed: {e}") from e