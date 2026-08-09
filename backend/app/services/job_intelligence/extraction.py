# backend/app/services/job_intelligence/extraction.py
import json

from app.core.llm import chat_completion, MODEL
from app.prompts.job_intelligence import JOB_AND_COMPANY_EXTRACTION_SYSTEM_PROMPT
from app.schemas.job_intelligence import ExtractedJobAndCompany


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
    print(f"[TRACING] Extracting job+company data from text (length: {len(raw_text)} chars)...", flush=True)
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
        print(f"[TRACING] Raw job+company extraction JSON:\n{content}", flush=True)
        return ExtractedJobAndCompany.model_validate(json.loads(content))
    except Exception as e:
        print(f"[TRACING] Job+company extraction failed: {e}", flush=True)
        raise JobIntelligenceExtractionError(f"Job+company extraction LLM call failed: {e}") from e