import os
import asyncio
from dotenv import load_dotenv
import asyncpg

load_dotenv("apps/api/.env", override=False)
db_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

async def main():
    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch("""
            SELECT pid, usename, client_addr, state, xact_start, query 
            FROM pg_stat_activity 
            WHERE pid <> pg_backend_pid() 
              AND backend_type = 'client backend' 
              AND (state != 'idle' OR xact_start IS NOT NULL);
        """)
        print(f"Quiescent Check: Found {len(rows)} active/non-idle sessions.")
        for r in rows:
            print(f"  PID {r['pid']} | User: {r['usename']} | State: {r['state']} | Xact Start: {r['xact_start']} | Query: {r['query']}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())

