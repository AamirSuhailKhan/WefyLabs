import asyncio
import json
import os
from datetime import datetime
import asyncpg

env_path = r"C:\Users\aamir\OneDrive\Desktop\crm real state\apps\api\.env"
if os.path.exists(env_path):
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    org_id = "a0317351-e076-493e-8b84-182f8c43666e"
    pilot_id = "d153ea17-b2d3-40ab-b258-75951ef7de28"

    print("=== LEADS FOR ORG ===")
    leads = await conn.fetch(
        "SELECT id, organization_id, broker_id, name, email, phone, status, created_at FROM leads WHERE organization_id = $1 ORDER BY created_at DESC",
        org_id
    )
    for l in leads:
        print(dict(l))

    print("\n=== SALES LOOP EVENTS FOR ORG ===")
    events = await conn.fetch(
        "SELECT * FROM sales_loop_events WHERE tenant_id = $1 OR tenant_id = $2 ORDER BY created_at DESC",
        org_id, pilot_id
    )
    for e in events:
        d = dict(e)
        if isinstance(d.get("payload"), str):
            try:
                d["payload"] = json.loads(d["payload"])
            except:
                pass
        print(d)

    print("\n=== PILOT OBSERVATIONS FOR ORG ===")
    obs = await conn.fetch(
        "SELECT * FROM pilot_observations WHERE organization_id = $1 ORDER BY created_at DESC",
        org_id
    )
    for o in obs:
        print(dict(o))

    print("\n=== PILOT HUMAN DECISIONS FOR ORG ===")
    decs = await conn.fetch(
        "SELECT * FROM pilot_human_decisions WHERE organization_id = $1 ORDER BY created_at DESC",
        org_id
    )
    for d in decs:
        print(dict(d))

    print("\n=== PILOT AUDIT EVENTS FOR PILOT ===")
    audits = await conn.fetch(
        "SELECT id, pilot_id, sequence_number, event_type, actor_id, actor_email, occurred_at FROM pilot_audit_events WHERE pilot_id = $1 ORDER BY sequence_number ASC",
        pilot_id
    )
    for a in audits:
        print(dict(a))

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
