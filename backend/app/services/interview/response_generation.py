"""Single LLM call that does ALL reasoning for the Interview Response
Agent: question classification, competency judgment, story selection,
sufficiency judgment, and answer generation. This module does not
decide any of that itself — it only (a) calls the model and (b) retries
if the model's output isn't parseable JSON, which is a plumbing concern,
not a content decision. If generation genuinely fails, we surface that
failure rather than writing a fallback answer ourselves.
"""
import json

from app.core.llm import client, MODEL
from app.prompts.interview_response import INTERVIEW_RESPONSE_SYSTEM_PROMPT
from app.schemas.interview_response import InterviewLLMOutput

MAX_ATTEMPTS = 3


class InterviewGenerationError(Exception):
    """Raised when the model's output couldn't be obtained/parsed after
    all retries. Callers should surface this as a failure to the user —
    NOT synthesize a templated answer, since that would reintroduce a
    deterministic content decision.
    """


async def generate_interview_response(context: dict) -> InterviewLLMOutput:
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(
            f"[TRACING] Requesting interview response (attempt {attempt}/{MAX_ATTEMPTS}) "
            f"for question={context['question']!r}...",
            flush=True,
        )
        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": INTERVIEW_RESPONSE_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(context)},
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
            )
            content = response.choices[0].message.content
            print(f"[TRACING] Raw interview response JSON:\n{content}", flush=True)
            parsed = InterviewLLMOutput.model_validate(json.loads(content))
            print(f"[TRACING] Blueprint used: {parsed.blueprint_used}", flush=True)
            return parsed
        except Exception as e:
            print(f"[TRACING] Attempt {attempt}/{MAX_ATTEMPTS} failed to parse: {e}", flush=True)
            last_error = e

    raise InterviewGenerationError(
        f"Interview response generation failed after {MAX_ATTEMPTS} attempts: {last_error}"
    )