import asyncio, os, sys, json, base64
sys.path.insert(0, r"c:\Users\aamir\OneDrive\Desktop\crm real state\apps\api")
from app.config import settings
import redis.asyncio as aioredis

async def main():
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    items = await r.lrange("sales-loop-orchestration", 0, 9)
    print(f"Total items in 'sales-loop-orchestration': {len(items)}")
    for i, item in enumerate(items):
        try:
            parsed = json.loads(item)
            # Celery message body is base64 encoded or json
            headers = parsed.get("headers", {})
            body = parsed.get("body", "")
            try:
                decoded_body = json.loads(base64.b64decode(body).decode('utf-8'))
            except Exception:
                decoded_body = body
            print(f"\n--- Item {i} ---")
            print(f"Task: {headers.get('task') or parsed.get('task')}")
            print(f"ID:   {headers.get('id') or parsed.get('id')}")
            print(f"Body: {json.dumps(decoded_body, indent=2)}")
        except Exception as e:
            print(f"Item {i} raw: {item[:200]} (err: {e})")
            
    await r.aclose()

asyncio.run(main())
