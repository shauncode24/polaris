import json
from app.core.llm import client, MODEL
from app.schemas.extraction import ExtractionResult

SYSTEM_PROMPT = """You are a resume parser. Extract structured data from resume text.
Output ONLY valid JSON matching this schema, no prose, no markdown fences:
{
  "experiences": [{"role": str, "company": str, "start_date": str|null, "end_date": str|null, "stack": [str], "bullets": [str]}],
  "projects": [{"name": str, "description": str, "stack": [str]}],
  "skills": [str]
}
Only extract what is explicitly present in the text. Do not invent companies, projects, or skills.
For every project, "description" is REQUIRED and must never be null or an empty string. Copy the
resume's own description text for that project verbatim — including the "Tools: ..." line and every
following bullet/sentence for that project — so no detail from the source text is lost.
For each project and each experience, the "stack" array MUST include every technology, language,
framework, tool, or platform mentioned anywhere in that project's or experience's own text
(description or bullets) — not just the headline technologies.
The top-level "skills" list and every "stack" array must contain ONLY concrete technologies,
languages, frameworks, libraries, tools, or platforms.
If a skill only appears in the resume's general skills section and is not tied to any specific
project or experience, still include it once in the top-level "skills" list, but do not fabricate
a stack/bullet reference for it."""


async def extract_resume_data(raw_text: str) -> ExtractionResult:
    print(f"[TRACING] Extracting resume data from text (length: {len(raw_text)} chars)...", flush=True)
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
    print(f"[TRACING] Raw LLM JSON response:\n{content}", flush=True)
    return ExtractionResult.model_validate(json.loads(content))