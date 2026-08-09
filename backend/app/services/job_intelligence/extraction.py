# backend/app/services/job_intelligence/extraction.py
import json

from app.core.llm import chat_completion, MODEL
from app.prompts.job_intelligence import JOB_AND_COMPANY_EXTRACTION_SYSTEM_PROMPT
from app.schemas.job_intelligence import ExtractedJobAndCompany


async def extract_job_and_company(raw_text: str) -> ExtractedJobAndCompany:
    """ONE LLM call producing both role-level and company-level
    extraction (design doc revision, "One Input, One LLM Call") — the
    backend splits this into two independent profiles immediately after
    parsing; see job_intelligence/builder.py.
    """
    print(f"[TRACING] Extracting job+company data from text (length: {len(raw_text)} chars)...", flush=True)
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