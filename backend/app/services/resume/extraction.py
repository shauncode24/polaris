import logging

from app.core.llm import Prompt, llm_json
from app.schemas.resume.extraction import ExtractionResult

from app.prompts.resume.extraction import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def extract_resume_data(raw_text: str) -> ExtractionResult:
    logger.debug("Extracting resume data from text (length: %d chars)...", len(raw_text))
    reply = await llm_json(
        Prompt(SYSTEM_PROMPT, raw_text), ExtractionResult,
        label="resume_extraction", expect=("experiences", "projects", "education", "skills"),
    )
    return reply.value