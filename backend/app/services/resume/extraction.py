import json
from app.core.llm import chat_completion, MODEL
from app.schemas.resume.extraction import ExtractionResult

from app.prompts.resume.extraction import SYSTEM_PROMPT


async def extract_resume_data(raw_text: str) -> ExtractionResult:
    print(f"[TRACING] Extracting resume data from text (length: {len(raw_text)} chars)...", flush=True)
    response = await chat_completion(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content
    print(f"[TRACING] Raw LLM JSON response:\n{content}", flush=True)
    return ExtractionResult.model_validate(json.loads(content))