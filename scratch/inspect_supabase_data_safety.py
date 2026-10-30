import os
import asyncio
from dotenv import load_dotenv
import asyncpg

load_dotenv("apps/api/.env", override=False)
db_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

async def inspect():
    conn = await asyncpg.connect(db_url)
    try:
        tables = ['organizations', 'brokers', 'subscriptions', 'leads', 'source_attributions', 'alembic_version']
        print("--- Table Row Counts on Supabase ---")
        for t in tables:
            exists = await conn.fetchval(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{t}')")
            if exists:
                cnt = await conn.fetchval(f"SELECT count(*) FROM {t}")
                print(f"Table '{t}': {cnt} rows")
            else:
                print(f"Table '{t}': DOES NOT EXIST")

        print("\n--- source_attributions Column Types on Supabase ---")
        cols = await conn.fetch("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'source_attributions'
            ORDER BY ordinal_position
        """)
        for c in cols:
            print(f"  {c['column_name']}: {c['data_type']} (nullable={c['is_nullable']})")

        print("\n--- Inspecting source_attributions data for UUID validity ---")
        rows = await conn.fetch("SELECT id, organization_id, lead_id FROM source_attributions LIMIT 20")
        print(f"Sample source_attributions ({len(rows)} rows):")
        for r in rows:
            print(f"  id={r['id']}, org_id={r['organization_id']}, lead_id={r['lead_id']}")

        # Check if any org_id is not a valid UUID
        invalid_orgs = await conn.fetch("""
            SELECT id, organization_id FROM source_attributions 
            WHERE organization_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        """)
        print(f"Invalid UUIDs in organization_id: {len(invalid_orgs)}")

        # Check if any lead_id is not a valid UUID (when not null)
        invalid_leads = await conn.fetch("""
            SELECT id, lead_id FROM source_attributions 
            WHERE lead_id IS NOT NULL 
              AND lead_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        """)
        print(f"Invalid UUIDs in lead_id: {len(invalid_leads)}")

        # Check if any organization_id doesn't exist in organizations table
        orphan_orgs = await conn.fetch("""
            SELECT count(*) FROM source_attributions sa
            WHERE NOT EXISTS (SELECT 1 FROM organizations o WHERE o.id::text = sa.organization_id::text)
        """)
        print(f"Orphaned organization_id in source_attributions: {orphan_orgs[0]['count']}")

        # Check if any lead_id doesn't exist in leads table
        orphan_leads = await conn.fetch("""
            SELECT count(*) FROM source_attributions sa
            WHERE sa.lead_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM leads l WHERE l.id::text = sa.lead_id::text)
        """)
        print(f"Orphaned lead_id in source_attributions: {orphan_leads[0]['count']}")

        print("\n--- Check Constraints on brokers & subscriptions on Supabase ---")
        checks = await conn.fetch("""
            SELECT conname, pg_get_constraintdef(oid) as def 
            FROM pg_constraint 
            WHERE conname LIKE 'ck_brokers%' OR conname LIKE 'ck_subscriptions%'
        """)
        for chk in checks:
            print(f"  {chk['conname']}: {chk['def']}")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect())

