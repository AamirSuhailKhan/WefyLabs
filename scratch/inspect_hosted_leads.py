import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv(".env")
remote_url = os.environ.get("DATABASE_URL").replace("+asyncpg", "")

async def inspect():
    c = await asyncpg.connect(remote_url)
    lead = await c.fetchrow("SELECT id, organization_id, name, deleted_at FROM leads WHERE id::text = $1", "c6a46685-ab96-4cb8-b3bc-8cef6b0f39e3")
    print("Orphaned lead in leads table:", lead)
    
    all_leads = await c.fetch("SELECT id, organization_id, name FROM leads")
    print("Total leads:", len(all_leads))
    for l in all_leads:
        print("  lead:", dict(l))
    await c.close()

if __name__ == "__main__":
    asyncio.run(inspect())
