import asyncio, os, sys
sys.path.insert(0, r"c:\Users\aamir\OneDrive\Desktop\crm real state\apps\api")
from app.config import settings
import redis.asyncio as aioredis

async def main():
    print("Connecting to Redis:", settings.REDIS_URL[:25], "...")
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    ping = await r.ping()
    print("Redis Ping:", ping)
    
    queues = ["sales-loop-orchestration", "lead_queue", "celery", "default", "email_queue"]
    for q in queues:
        try:
            length = await r.llen(q)
            print(f"Queue '{q}' length: {length}")
        except Exception as e:
            print(f"Queue '{q}' error: {e}")
            
    await r.aclose()

asyncio.run(main())
