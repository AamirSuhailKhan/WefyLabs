import os
import asyncio
from urllib.parse import urlparse
from dotenv import load_dotenv
import asyncpg

load_dotenv("apps/api/.env", override=False)
db_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

async def check():
    p = urlparse(db_url)
    print(f"Connecting to host={p.hostname}, port={p.port}, db={p.path}...")
    try:
        conn = await asyncio.wait_for(asyncpg.connect(db_url), timeout=5.0)
        try:
            ver = await conn.fetchval("SHOW server_version")
            rev = await conn.fetchval("SELECT version_num FROM alembic_version")
            print(f"Connection SUCCESS: server_version={ver}, alembic_revision={rev}")
        finally:
            await conn.close()
    except Exception as e:
        print(f"Connection FAILED: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(check())

