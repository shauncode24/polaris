import json
from app.core.llm import client, MODEL
from app.schemas.extraction import ExtractionResult

SYSTEM_PROMPT = """You are a resume parser. Extract structured data from resume text.
Output ONLY valid JSON matching this schema, no prose, no markdown fences:
{
  "experiences": [{"role": str, "company": str, "start_date": str|null, "end_date": str|null, "stack": [str], "bullets": [str]}],
  "projects": [{"name": str, "description": str|null, "stack": [str]}],
  "skills": [str]
}
Only extract what is explicitly present in the text. Do not invent companies, projects, or skills."""


async def extract_resume_data(raw_text: str) -> ExtractionResult:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content
    return ExtractionResult.model_validate(json.loads(content))