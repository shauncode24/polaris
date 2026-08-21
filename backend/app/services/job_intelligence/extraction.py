# backend/app/services/job_intelligence/extraction.py
import json
import logging

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


async def extract_job_and_company(raw_text: str) -> ExtractedJobAndCompany:
    """ONE LLM call producing both role-level and company-level
    extraction (design doc revision, "One Input, One LLM Call") — the
    backend splits this into two independent profiles immediately after
    parsing; see job_intelligence/builder.py.
    """
    logger.debug("Extracting job+company data from text (length: %d chars)...", len(raw_text))
    try:
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": JOB_AND_COMPANY_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        logger.debug("Raw job+company extraction JSON:\n%s", content)
        return ExtractedJobAndCompany.model_validate(json.loads(content))
    except Exception as e:
        logger.warning("Job+company extraction failed: %s", e)
        raise JobIntelligenceExtractionError(f"Job+company extraction LLM call failed: {e}") from e