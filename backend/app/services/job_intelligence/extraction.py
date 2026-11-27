# backend/app/services/job_intelligence/extraction.py
import json
import logging

from openai import BadRequestError

from app.core.llm import chat_completion, MODEL
from app.prompts.job_intelligence.extraction import JOB_AND_COMPANY_EXTRACTION_SYSTEM_PROMPT
from app.schemas.job_intelligence.job_intelligence import ExtractedJobAndCompany

logger = logging.getLogger(__name__)


class JobIntelligenceExtractionError(Exception):
    """Raised when the combined job+company extraction LLM call fails or
    returns something we can't validate. Unlike most LLM calls elsewhere
    in this codebase (prioritization, narrative, weekly brief, ...),
    there is deliberately NO deterministic fallback here — the entire
    Job Intelligence pipeline (normalization, seniority, keywords,
    interview focus, and everything the Comparison Engine later reads)
    depends on this one extraction succeeding. Callers must surface this
    as a real failure (see api/jobs.py and api/job_intelligence.py,
    which translate it into an HTTP 502) rather than silently degrading
    into an empty/garbage profile the rest of the pipeline would then
    treat as real.
    """


_ATTEMPTS = 2
# The sections a finished reply always has. The schema defaults every one of
# them to empty, so a reply that stops early would otherwise validate and
# silently lose requirements.
_EXPECTED_JOB_KEYS = ("required_skills", "implicit_skills", "nice_to_have", "qualification_requirements")


def is_complete_reply(payload) -> bool:
    job = payload.get("job") if isinstance(payload, dict) else None
    return isinstance(job, dict) and "company" in payload and all(key in job for key in _EXPECTED_JOB_KEYS)


def _model_options() -> dict:
    # Reasoning shares the reply's token allowance. At the default effort the
    # gpt-oss models often ran out partway through the JSON.
    return {"reasoning_effort": "low"} if "gpt-oss" in MODEL else {}


async def _request_extraction(raw_text: str) -> ExtractedJobAndCompany:
    response = await chat_completion(
        model=MODEL,
        messages=[
            {"role": "system", "content": JOB_AND_COMPANY_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        **_model_options(),
    )
    content = response.choices[0].message.content
    logger.debug("Raw job+company extraction JSON:\n%s", content)
    payload = json.loads(content)
    if not is_complete_reply(payload):
        raise ValueError("the reply stopped before every section was written")
    return ExtractedJobAndCompany.model_validate(payload)


async def extract_job_and_company(raw_text: str) -> ExtractedJobAndCompany:
    """ONE LLM call producing both role-level and company-level
    extraction (design doc revision, "One Input, One LLM Call") — the
    backend splits this into two independent profiles immediately after
    parsing; see job_intelligence/builder.py.

    An unusable reply (cut off, not JSON, wrong shape) is asked for once
    more. Anything else, such as a bad key or an outage, fails at once; the
    client already retries rate limits and server errors.
    """
    logger.debug("Extracting job+company data from text (length: %d chars)...", len(raw_text))
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            return await _request_extraction(raw_text)
        except Exception as e:
            unusable_reply = isinstance(e, ValueError) or (
                isinstance(e, BadRequestError) and e.code == "json_validate_failed"
            )
            if unusable_reply and attempt < _ATTEMPTS:
                logger.warning("Job+company extraction reply unusable, retrying: %s", e)
                continue
            logger.warning("Job+company extraction failed: %s", e)
            raise JobIntelligenceExtractionError(f"Job+company extraction LLM call failed: {e}") from e