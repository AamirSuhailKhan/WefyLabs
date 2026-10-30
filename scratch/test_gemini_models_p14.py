import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.abspath("apps/api"))

from app.config import settings
from app.modules.ai_agent.llm_router.adapters.google_adapter import GoogleAdapter

async def test_single_model(key, model_id):
    print(f"\n[Test] Calling GoogleAdapter with model='{model_id}'...", flush=True)
    adapter = GoogleAdapter(api_key=key, model=model_id)
    print(f"[Test] Resolved target model: {adapter._model}", flush=True)
    
    t0 = time.time()
    try:
        # Wrap complete in asyncio.wait_for with a 20s timeout
        resp = await asyncio.wait_for(
            adapter.complete(
                messages=[{"role": "user", "content": "Respond with the single word PONG"}],
                max_tokens=10,
                temperature=0.0
            ),
            timeout=25.0
        )
        dur = time.time() - t0
        print(f"[Result] Model: {model_id} | Success: {resp.success} | Latency: {dur:.2f}s", flush=True)
        if resp.success:
            print(f"[Result] Content: {resp.content!r}", flush=True)
            print(f"[Result] Model Used: {resp.model}", flush=True)
            print(f"[Result] Tokens: prompt={resp.prompt_tokens}, completion={resp.completion_tokens}", flush=True)
        else:
            print(f"[Result] Error: {resp.error}", flush=True)
        return resp
    except asyncio.TimeoutError:
        print(f"[Result] TIMEOUT (25s) on model {model_id}", flush=True)
        return None
    except Exception as exc:
        print(f"[Result] Exception: {exc}", flush=True)
        return None

async def main():
    key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not key or key.startswith("placeholder"):
        print("GEMINI_API_KEY: NOT_CONFIGURED", flush=True)
        return

    print(f"Key configured: True (Length: {len(key)}, Prefix: {key[:4]}***)", flush=True)
    os.environ["ALLOW_LIVE_AI_CALLS_IN_TESTS"] = "1"

    # Test gemini-3.8-flash first
    await test_single_model(key, "gemini-3.8-flash")
    
    # Test gemini-3.5-flash
    await test_single_model(key, "gemini-3.5-flash")
    
    # Test gemini-2.5-flash
    await test_single_model(key, "gemini-2.5-flash")

if __name__ == "__main__":
    asyncio.run(main())
