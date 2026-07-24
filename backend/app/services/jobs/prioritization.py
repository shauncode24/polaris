import json

from app.core.llm import client, MODEL
from app.prompts.jd_prioritization import PRIORITIZATION_SYSTEM_PROMPT
from app.schemas.prioritization import PrioritizationResult


class PrioritizationError(Exception):
    """Raised when the contextual-reasoning LLM call fails or returns something
    we can't trust. Callers should catch this and fall back to the deterministic
    frequency + flat-rate estimate — same graceful-degradation pattern the
    LeetCode sync uses for its unofficial endpoint (see LeetCodeSyncError)."""


async def prioritize_missing_skills(context: dict) -> PrioritizationResult:
    print(
        f"[TRACING] Requesting LLM prioritization for {len(context.get('missing', []))} missing skills...",
        flush=True,
    )
    try:
        response = await client.chat.completions.create(
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