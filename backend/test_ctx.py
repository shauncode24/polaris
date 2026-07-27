import asyncio
import os
import json
from openai import AsyncOpenAI

async def test():
    client = AsyncOpenAI(
        base_url="http://host.docker.internal:11434/v1",
        api_key="ollama",
    )
    model = "gemma3:4b"

    # Make a very large prompt of about 6000 tokens
    large_prose = "This is a repeating sentence to fill the context. " * 800
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Output ONLY valid JSON matching this schema: {\"reply\": str}"},
        {"role": "user", "content": f"Context: {large_prose}\n\nQuestion: Summarize the context in one word."}
    ]

    print("--- Test 1: WITHOUT specifying num_ctx ---")
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"}
        )
        print("Response:")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")

    print("\n--- Test 2: WITH num_ctx in extra_body (options) ---")
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            extra_body={"options": {"num_ctx": 16384}}
        )
        print("Response:")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
