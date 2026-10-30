import asyncio
import json
import os
import sys
from dotenv import dotenv_values

sys.path.insert(0, os.path.abspath("apps/api"))

from app.modules.ai_agent.llm_router.adapters.google_adapter import GoogleAdapter

async def test_live_inference():
    print("--- TESTING LIVE GOOGLE GEMINI INFERENCE ---")
    
    # Load API key
    vals = dotenv_values(".env.pilot")
    api_key = vals.get("GOOGLE_API_KEY") or vals.get("GEMINI_API_KEY")
    if not api_key:
        vals = dotenv_values(".env")
        api_key = vals.get("GOOGLE_API_KEY") or vals.get("GEMINI_API_KEY")
        
    if not api_key or "OPERATOR" in api_key or "placeholder" in api_key.lower():
        print("STATUS: BLOCKED (No valid Google API key found in .env.pilot or .env)")
        return False

    print("API Key present in environment (length:", len(api_key), "chars)")
    
    # Set flag to permit live call in test context
    os.environ["ALLOW_LIVE_AI_CALLS_IN_TESTS"] = "1"
    os.environ["ENV"] = "pilot"

    # Test with gemini-2.5-flash and gemini-3.6-flash
    for test_model in ["gemini-2.5-flash", "gemini-3.6-flash"]:
        print(f"\nAttempting synthetic live completion with model: {test_model}")
        adapter = GoogleAdapter(api_key=api_key, model=test_model)
        
        messages = [
            {"role": "system", "content": "You are a real-estate AI assistant. Always output valid JSON strictly."},
            {"role": "user", "content": "Evaluate this lead: Name: Vikram, Budget: 2.5 Cr INR. Output JSON: {\"qualified\": true, \"tier\": \"hot\"}"}
        ]
        
        try:
            resp = await adapter.complete(messages=messages, max_tokens=150, temperature=0.1)
            print(f"Response Success: {resp.success}")
            print(f"Response Model: {resp.model}")
            print(f"Finish Reason: {resp.finish_reason}")
            print(f"Usage - Input Tokens: {resp.usage.prompt_tokens}, Output Tokens: {resp.usage.completion_tokens}")
            print(f"Calculated Cost: ${resp.cost:.6f}")
            print(f"Latency: {resp.latency_ms}ms")
            if resp.success:
                print(f"Content: {resp.content}")
                try:
                    parsed = json.loads(resp.content.strip("`").replace("json\n", ""))
                    print(f"JSON Parsed Successfully: {parsed}")
                except Exception as e:
                    print(f"JSON Parse Warning: {e}")
            else:
                print(f"Error Message: {resp.error}")
        except Exception as e:
            print(f"Exception during call: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_live_inference())

