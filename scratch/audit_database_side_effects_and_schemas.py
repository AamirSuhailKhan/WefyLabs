import os
import asyncio
import json
from dotenv import load_dotenv
import asyncpg

load_dotenv("apps/api/.env", override=False)
raw_supabase_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")
local_url = "postgresql://postgres:postgres@127.0.0.1:5432/leadscore"

async def main():
    print("--- 1. Querying Hosted Supabase Schema & Table Breakdown ---")
    conn_sb = await asyncpg.connect(raw_supabase_url)
    try:
        sb_schemas = await conn_sb.fetch("""
            SELECT table_schema, count(*) as table_count
            FROM information_schema.tables
            GROUP BY table_schema
            ORDER BY count(*) DESC;
        """)
        print("Hosted Supabase table counts by schema:")
        total_sb = 0
        sb_breakdown = {}
        for r in sb_schemas:
            print(f"  Schema: {r['table_schema']:<30} Count: {r['table_count']}")
            total_sb += r['table_count']
            sb_breakdown[r['table_schema']] = r['table_count']
        print(f"Total tables across all schemas on Supabase: {total_sb}")

        # Specifically in 'public' schema:
        public_tables_sb = await conn_sb.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        print(f"Public tables on Hosted Supabase: {len(public_tables_sb)}")

        # Check brokers in hosted Supabase
        brokers_sb = await conn_sb.fetch("""
            SELECT *
            FROM brokers
            ORDER BY created_at ASC;
        """)
        print(f"\nBrokers currently in Hosted Supabase ({len(brokers_sb)}):")
        for b in brokers_sb:
            print(f"  Broker: {dict(b)}")

        # Check source attributions in hosted Supabase
        sa_sb = await conn_sb.fetch("""
            SELECT sa.id, sa.organization_id, sa.lead_id, sa.source_id, sa.channel, sa.provider, sa.created_at
            FROM source_attributions sa
            ORDER BY sa.created_at ASC;
        """)
        print(f"\nSource Attributions currently in Hosted Supabase ({len(sa_sb)}):")
        for s in sa_sb:
            print(f"  ID: {s['id']} | Org: {s['organization_id']} | Lead: {s['lead_id']} | Source: {s['source_id']} | Created: {s['created_at']}")

    finally:
        await conn_sb.close()

    print("\n--- 2. Querying Local Docker 'leadscore' Schema & Table Breakdown ---")
    try:
        conn_loc = await asyncpg.connect(local_url)
        try:
            loc_schemas = await conn_loc.fetch("""
                SELECT table_schema, count(*) as table_count
                FROM information_schema.tables
                GROUP BY table_schema
                ORDER BY count(*) DESC;
            """)
            print("Local Docker table counts by schema:")
            total_loc = 0
            loc_breakdown = {}
            for r in loc_schemas:
                print(f"  Schema: {r['table_schema']:<30} Count: {r['table_count']}")
                total_loc += r['table_count']
                loc_breakdown[r['table_schema']] = r['table_count']
            print(f"Total tables across all schemas on Local Docker: {total_loc}")

            public_tables_loc = await conn_loc.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            print(f"Public tables on Local Docker: {len(public_tables_loc)}")

            # Compare public tables
            sb_set = set(r['table_name'] for r in public_tables_sb)
            loc_set = set(r['table_name'] for r in public_tables_loc)
            diff_sb_minus_loc = sb_set - loc_set
            diff_loc_minus_sb = loc_set - sb_set
            print(f"Public tables in Supabase but not Local Docker: {diff_sb_minus_loc}")
            print(f"Public tables in Local Docker but not Supabase: {diff_loc_minus_sb}")

            # Save json report
            out = {
                "hosted_supabase": {
                    "total_tables": total_sb,
                    "by_schema": sb_breakdown,
                    "public_count": len(public_tables_sb)
                },
                "local_docker": {
                    "total_tables": total_loc,
                    "by_schema": loc_breakdown,
                    "public_count": len(public_tables_loc)
                },
                "public_table_diff": {
                    "in_sb_not_loc": list(diff_sb_minus_loc),
                    "in_loc_not_sb": list(diff_loc_minus_sb)
                }
            }
            with open("scratch/table_schema_breakdown.json", "w") as f:
                json.dump(out, f, indent=2)

        finally:
            await conn_loc.close()
    except Exception as e:
        print(f"Local Docker query error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
