import json
import os
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    api_key="ollama",  # required by the SDK, unused by Ollama
)

MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")


def clean_json_content(content: str) -> str:
    if not content:
        return content
    content = content.strip()

    # Find the bounds of the JSON structure (object or array)
    start_chars = {"{", "["}
    start_idx = -1
    for i, char in enumerate(content):
        if char in start_chars:
            start_idx = i
            break

    if start_idx != -1:
        end_char = "}" if content[start_idx] == "{" else "]"
        end_idx = content.rfind(end_char)
        if end_idx != -1 and end_idx > start_idx:
            raw_json = content[start_idx : end_idx + 1]
            try:
                # Parse with strict=False to allow unescaped control characters (like newlines, tabs)
                parsed = json.loads(raw_json, strict=False)
                # Re-serialize to guarantee standard, properly escaped JSON format
                return json.dumps(parsed)
            except Exception:
                # Fallback if json load/dump fails
                return raw_json

    return content



async def chat_completion(*args, **kwargs):
    base_url_str = str(client.base_url).lower()
    is_ollama = (
        "ollama" in base_url_str
        or "localhost" in base_url_str
        or "127.0.0.1" in base_url_str
        or "host.docker.internal" in base_url_str
    )

    prefilled_json = False
    has_json_format = False
    if "response_format" in kwargs:
        has_json_format = True
        if is_ollama:
            messages = kwargs.get("messages", [])
            if messages and messages[-1].get("role") != "assistant":
                kwargs["messages"] = list(messages) + [{"role": "assistant", "content": "{"}]
                prefilled_json = True

    response = await client.chat.completions.create(*args, **kwargs)

    if has_json_format:
        content = response.choices[0].message.content
        if prefilled_json and content:
            content = content.strip()
            if not content.startswith("{") and not content.startswith("["):
                content = "{" + content
        cleaned = clean_json_content(content)
        response.choices[0].message.content = cleaned

    return response
