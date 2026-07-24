import os
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    api_key="ollama",  # required by the SDK, unused by Ollama
)

MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")