"""Verify Redis connection"""
import asyncio
import redis.asyncio as aioredis
from app.config import settings

async def check_redis():
    print(f"Connecting to Redis at {settings.REDIS_URL[:30]}...")
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        pong = await client.ping()
        print("Redis PING:", pong)
        info = await client.info("server")
        print("Redis version:", info.get("redis_version"))
        print("Redis mode:", info.get("redis_mode"))
        dbsize = await client.dbsize()
        print("DB keys count:", dbsize)
    except Exception as e:
        print("Redis connection error:", e)
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(check_redis())
