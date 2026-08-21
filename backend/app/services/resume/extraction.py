import json
import logging

from app.core.llm import chat_completion, MODEL
from app.schemas.resume.extraction import ExtractionResult

from app.prompts.resume.extraction import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def extract_resume_data(raw_text: str) -> ExtractionResult:
    logger.debug("Extracting resume data from text (length: %d chars)...", len(raw_text))
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
    logger.debug("Raw LLM JSON response:\n%s", content)
    return ExtractionResult.model_validate(json.loads(content))