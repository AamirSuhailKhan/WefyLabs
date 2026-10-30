import os
import asyncio
from dotenv import load_dotenv
import asyncpg

load_dotenv("apps/api/.env", override=False)
db_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

async def main():
    conn = await asyncpg.connect(db_url)
    try:
        org_ids = ['ffe80022-9c74-4221-ad34-1c467a181c54', 'a7acf8e1-ca47-42b5-bef6-a6a29fde6087', '530a0335-5969-41d3-b5af-52d13e9ac393']
        for oid in org_ids:
            e = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM organizations WHERE id::text = $1)", oid)
            print(f"org {oid} exists: {e}")

        lead_ids = ['c6a46685-ab96-4cb8-b3bc-8cef6b0f39e3', '38191ec5-fe71-4800-9ef2-ab1a0fbd30e8', '0151931c-efd4-46af-b6fd-136837923cc7']
        for lid in lead_ids:
            e = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM leads WHERE id::text = $1)", lid)
            print(f"lead {lid} exists: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())

