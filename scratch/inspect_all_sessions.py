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
            SELECT pid, usename, client_addr, state, backend_type, application_name, xact_start 
            FROM pg_stat_activity 
            WHERE pid <> pg_backend_pid();
        """)
        print(f"Total other sessions on Supabase: {len(rows)}")
        for r in rows:
            print(f"  PID {r['pid']} | User: {r['usename']} | App: {r['application_name']} | State: {r['state']} | Xact Start: {r['xact_start']}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())

