# backend/app/services/job_intelligence/extraction.py
import logging

from app.core.llm import LLMError, Prompt, llm_json
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


# The sections a finished reply always has. The schema defaults every one of
# them to empty, so a reply that stops early would otherwise validate and
# silently lose requirements.
_EXPECTED_JOB_KEYS = ("required_skills", "implicit_skills", "nice_to_have", "qualification_requirements")


def is_complete_reply(payload) -> bool:
    job = payload.get("job") if isinstance(payload, dict) else None
    return isinstance(job, dict) and "company" in payload and all(key in job for key in _EXPECTED_JOB_KEYS)


def _require_complete(payload: dict) -> dict:
    if not is_complete_reply(payload):
        raise ValueError("the reply stopped before every section was written")
    return payload


async def extract_job_and_company(raw_text: str) -> ExtractedJobAndCompany:
    """ONE LLM call producing both role-level and company-level
    extraction (design doc revision, "One Input, One LLM Call") — the
    backend splits this into two independent profiles immediately after
    parsing; see job_intelligence/builder.py.

    A cut-off or unreadable reply is asked for once more (see core/llm.py).
    """
    logger.debug("Extracting job+company data from text (length: %d chars)...", len(raw_text))
    try:
        reply = await llm_json(
            Prompt(JOB_AND_COMPANY_EXTRACTION_SYSTEM_PROMPT, raw_text), ExtractedJobAndCompany,
            label="job_extraction", prepare=_require_complete,
        )
    except LLMError as e:
        raise JobIntelligenceExtractionError(str(e)) from e
    return reply.value
