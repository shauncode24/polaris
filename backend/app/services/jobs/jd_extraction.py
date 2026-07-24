import json

from app.core.llm import client, MODEL
from app.prompts.jd_extraction import JD_SYSTEM_PROMPT
from app.schemas.skill_gap import ExtractedJDRequirements


async def extract_jd_requirements(raw_text: str) -> ExtractedJDRequirements:
    print(f"[TRACING] Extracting JD requirements (text length: {len(raw_text)} chars)...", flush=True)
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": JD_SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content
    print(f"[TRACING] Raw JD extraction JSON:\n{content}", flush=True)
    return ExtractedJDRequirements.model_validate(json.loads(content))