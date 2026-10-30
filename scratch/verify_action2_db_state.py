import asyncio
import asyncpg
import json

async def inspect_db_state(url: str, db_name: str):
    conn = await asyncpg.connect(url)
    
    # Revision
    rev = await conn.fetchval("SELECT version_num FROM alembic_version;")
    
    # source_attributions columns
    cols = await conn.fetch("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'source_attributions' AND table_schema = 'public'
        ORDER BY ordinal_position;
    """)
    cols_data = [{
        "column": r["column_name"],
        "type": r["data_type"],
        "nullable": r["is_nullable"],
        "default": r["column_default"]
    } for r in cols]
    
    # source_attributions constraints
    cons = await conn.fetch("""
        SELECT conname, contype, pg_get_constraintdef(oid) as def
        FROM pg_constraint
        WHERE conrelid = 'source_attributions'::regclass
        ORDER BY conname;
    """)
    cons_data = [{
        "name": r["conname"],
        "type": r["contype"].decode("ascii") if isinstance(r["contype"], bytes) else str(r["contype"]),
        "definition": r["def"]
    } for r in cons]
    
    # Table counts
    counts = {}
    for tbl in ["leads", "organizations", "brokers", "organization_members", "source_attributions", "tasks"]:
        cnt = await conn.fetchval(f"SELECT count(*) FROM {tbl};")
        counts[tbl] = cnt
        
    # Sample rows in source_attributions
    sample_rows = await conn.fetch("SELECT id, organization_id, lead_id, channel, provider, created_at FROM source_attributions LIMIT 5;")
    sample_data = [{
        "id": str(r["id"]),
        "organization_id": str(r["organization_id"]),
        "lead_id": str(r["lead_id"]) if r["lead_id"] is not None else None,
        "channel": r["channel"],
        "provider": r["provider"],
        "created_at": str(r["created_at"])
    } for r in sample_rows]
    
    await conn.close()
    return {
        "database": db_name,
        "revision": rev,
        "table_counts": counts,
        "source_attributions_columns": cols_data,
        "source_attributions_constraints": cons_data,
        "source_attributions_samples": sample_data
    }

async def main():
    state_0048 = await inspect_db_state("postgresql://postgres:postgres@127.0.0.1:5432/leadscore", "leadscore (0048)")
    state_0049 = await inspect_db_state("postgresql://postgres:postgres@127.0.0.1:5432/leadscore_pilot", "leadscore_pilot (0049)")
    
    with open("scratch/verified_db_state_audit.json", "w") as f:
        json.dump({"leadscore_0048": state_0048, "leadscore_pilot_0049": state_0049}, f, indent=2)
    print("Action 2: Read-only DB verification complete. Saved to scratch/verified_db_state_audit.json")

if __name__ == "__main__":
    asyncio.run(main())
