import asyncio
import os
import sys
import time
import json

sys.path.insert(0, os.path.abspath("apps/api"))

from app.config import settings
from app.modules.ai_agent.llm_router.adapters.google_adapter import GoogleAdapter

async def evaluate_models():
    key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not key or key.startswith("placeholder"):
        print("GEMINI_API_KEY not configured or placeholder.")
        return

    os.environ["ALLOW_LIVE_AI_CALLS_IN_TESTS"] = "1"
    
    results = {}
    models_to_test = ["gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.5-flash"]

    for m in models_to_test:
        print(f"\nEvaluating model '{m}' via GoogleAdapter.complete()...", flush=True)
        adapter = GoogleAdapter(api_key=key, model=m)
        t0 = time.monotonic()
        try:
            resp = await asyncio.wait_for(
                adapter.complete(
                    messages=[{"role": "user", "content": "Respond with the single word PONG"}],
                    max_tokens=10,
                    temperature=0.0
                ),
                timeout=30.0
            )
            lat = int((time.monotonic() - t0) * 1000)
            print(f"Result for '{m}': success={resp.success}, latency={lat}ms, content={resp.content!r}, error={resp.error}", flush=True)
            results[m] = {
                "model_tested": m,
                "resolved_model": adapter._model,
                "success": resp.success,
                "latency_ms": lat,
                "content": resp.content,
                "prompt_tokens": resp.prompt_tokens,
                "completion_tokens": resp.completion_tokens,
                "error": resp.error
            }
        except asyncio.TimeoutError:
            lat = int((time.monotonic() - t0) * 1000)
            print(f"Result for '{m}': TIMEOUT after {lat}ms", flush=True)
            results[m] = {
                "model_tested": m,
                "resolved_model": adapter._model,
                "success": False,
                "latency_ms": lat,
                "error": f"Timeout after {lat}ms"
            }
        except Exception as exc:
            lat = int((time.monotonic() - t0) * 1000)
            print(f"Result for '{m}': EXCEPTION {exc}", flush=True)
            results[m] = {
                "model_tested": m,
                "resolved_model": adapter._model,
                "success": False,
                "latency_ms": lat,
                "error": str(exc)
            }

    with open("scratch/gemini_model_validation_p14_2.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\nSaved evaluation results to scratch/gemini_model_validation_p14_2.json", flush=True)

if __name__ == "__main__":
    asyncio.run(evaluate_models())
