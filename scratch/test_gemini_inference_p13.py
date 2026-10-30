"""
Test Gemini live API connectivity with minimal harmless synthetic prompt.
Zero customer data. Never prints the secret key.
"""
import asyncio
import os
import sys

# Ensure api app directory is in path
sys.path.insert(0, os.path.abspath("apps/api"))

from app.config import settings
from app.modules.ai_agent.llm_router.adapters.google_adapter import GoogleAdapter

async def main():
    key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not key:
        print("RESULT: KEY_MISSING")
        return

    print(f"Key configured: True (Length: {len(key)}, Prefix: {key[:4]}...)")
    
    # We must allow live AI call for this isolated test script
    os.environ["ALLOW_LIVE_AI_CALLS_IN_TESTS"] = "1"
    
    adapter = GoogleAdapter(api_key=key, model="gemini-2.0-flash")
    print(f"Provider: {adapter.provider_name}, Target model: {adapter._model}")
    
    # 1. Test is_available
    available = await adapter.is_available()
    print(f"is_available ping result: {available}")
    
    # 2. Minimal harmless prompt: "Respond with the word 'PONG'"
    response = await adapter.complete(
        messages=[{"role": "user", "content": "Respond with the single word PONG"}],
        max_tokens=10,
        temperature=0.0
    )
    
    print(f"complete() success: {response.success}")
    if response.success:
        print(f"Response content: {response.content!r}")
        print(f"Model used: {response.model}")
        print(f"Tokens: in={response.prompt_tokens}, out={response.completion_tokens}")
        print(f"Latency: {response.latency_ms}ms")
    else:
        print(f"Error: {response.error}")

if __name__ == "__main__":
    asyncio.run(main())
