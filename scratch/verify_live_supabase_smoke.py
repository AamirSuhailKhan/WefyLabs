import os
import asyncio
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
import asyncpg

load_dotenv("apps/api/.env", override=False)
raw_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

async def main():
    conn = await asyncpg.connect(raw_url)
    try:
        print("--- Testing Live Supabase Production Queries on Revision 0050 ---")
        rev = await conn.fetchval("SELECT version_num FROM alembic_version")
        print(f"Current Alembic revision: {rev}")
        assert rev == "0050_broker_subscription_constraint_parity", f"Wrong revision: {rev}"

        # 1. Test relational JOIN without type casting
        rows = await conn.fetch("""
            SELECT sa.id, sa.organization_id, sa.lead_id, o.name as org_name, l.name as lead_name
            FROM source_attributions sa
            JOIN organizations o ON sa.organization_id = o.id
            LEFT JOIN leads l ON sa.lead_id = l.id
        """)
        print(f"Successfully joined source_attributions with organizations and leads: {len(rows)} records found.")
        for r in rows:
            print(f"  Attr: {r['id']} | Org: {r['org_name']} ({r['organization_id']}) | Lead: {r['lead_name']} ({r['lead_id']})")

        # 2. Test inserting a valid SourceAttribution record with native UUIDs
        test_attr_id = str(uuid.uuid4())
        # Pick an existing organization and lead
        org_id = await conn.fetchval("SELECT id FROM organizations LIMIT 1")
        lead_id = await conn.fetchval("SELECT id FROM leads LIMIT 1")
        existing_source = await conn.fetchval("SELECT id FROM lead_sources LIMIT 1")
        print(f"\nInserting test attribution with org_id={org_id}, lead_id={lead_id}, source_id={existing_source}...")

        await conn.execute("""
            INSERT INTO source_attributions (
                id, organization_id, lead_id, source_id, channel, provider, created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7
            )
        """, test_attr_id, org_id, lead_id, existing_source, "web", "organic", datetime.now(timezone.utc))
        print("Insert succeeded without operator mismatch!")

        # 3. Test querying the inserted attribution by UUID
        queried = await conn.fetchrow("""
            SELECT sa.id, sa.organization_id, sa.lead_id, o.name as org_name, l.name as lead_name
            FROM source_attributions sa
            JOIN organizations o ON sa.organization_id = o.id
            JOIN leads l ON sa.lead_id = l.id
            WHERE sa.id = $1
        """, test_attr_id)
        assert queried is not None, "Failed to retrieve inserted attribution"
        print(f"Query succeeded: {dict(queried)}")

        # 4. Clean up test record
        await conn.execute("DELETE FROM source_attributions WHERE id = $1", test_attr_id)
        print("Cleaned up smoke test record cleanly.")

        # 5. Verify broker constraints accept modern values
        broker_id = await conn.fetchval("SELECT id FROM brokers LIMIT 1")
        if broker_id:
            await conn.execute("UPDATE brokers SET subscription_status = 'paused', subscription_plan = 'pro_monthly' WHERE id = $1", broker_id)
            print("Successfully updated broker to 'paused' and 'pro_monthly' (constraint 0050 verified!).")
            # Revert to active
            await conn.execute("UPDATE brokers SET subscription_status = 'active', subscription_plan = 'starter_monthly' WHERE id = $1", broker_id)

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
