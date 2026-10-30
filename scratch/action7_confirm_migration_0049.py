import asyncio
import asyncpg
import subprocess
import sys
import os
import uuid
import json

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
DISP_DB = "test_disposable_migration_0049"
DISP_URL = f"postgresql://postgres:postgres@127.0.0.1:5432/{DISP_DB}"

async def setup():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.execute(f"CREATE DATABASE {DISP_DB} WITH TEMPLATE leadscore;")
    await admin.close()
    print(f"[1] Created disposable database '{DISP_DB}' from 'leadscore' (revision 0048).")

async def tear_down():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.close()
    print(f"[CLEANUP] Dropped disposable database '{DISP_DB}'.")

def run_migration():
    print("[2] Executing 'alembic upgrade head' (Migration 0049) on disposable database...")
    api_dir = os.path.abspath("apps/api")
    cmd = [
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={DISP_URL}",
        "upgrade", "head"
    ]
    res = subprocess.run(cmd, cwd=api_dir, capture_output=True, text=True)
    assert res.returncode == 0, f"Migration failed: {res.stderr}"
    print("    Migration 0049 executed with exit code 0.")

async def verify_action7():
    conn = await asyncpg.connect(DISP_URL)
    report = {}

    # Check 1: Revision
    rev = await conn.fetchval("SELECT version_num FROM alembic_version;")
    assert rev == "0049_source_attribution_uuid_parity"
    report["target_revision"] = rev

    # Check 2: Column types
    cols = await conn.fetch("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'source_attributions' AND column_name IN ('organization_id', 'lead_id')
        ORDER BY column_name;
    """)
    cols_map = {r["column_name"]: (r["data_type"], r["is_nullable"]) for r in cols}
    assert cols_map["organization_id"] == ("uuid", "NO")
    assert cols_map["lead_id"] == ("uuid", "YES")
    report["column_types"] = cols_map

    # Check 3: Existing data preserved
    rows = await conn.fetch("SELECT id, organization_id, lead_id FROM source_attributions ORDER BY id;")
    assert len(rows) == 3, f"Expected 3 preserved rows, found {len(rows)}"
    report["preserved_row_count"] = len(rows)
    report["preserved_rows"] = [{"id": str(r["id"]), "organization_id": str(r["organization_id"]), "lead_id": str(r["lead_id"])} for r in rows]

    # Check 4: Foreign keys established
    fks = await conn.fetch("""
        SELECT conname, pg_get_constraintdef(oid) as def
        FROM pg_constraint
        WHERE conrelid = 'source_attributions'::regclass
        AND conname IN ('fk_source_attributions_organization_id', 'fk_source_attributions_lead_id')
        ORDER BY conname;
    """)
    fk_map = {r["conname"]: r["def"] for r in fks}
    assert "fk_source_attributions_organization_id" in fk_map
    assert "fk_source_attributions_lead_id" in fk_map
    report["foreign_keys"] = fk_map

    # Check 5: Deletion behavior (ON DELETE SET NULL)
    org_id = await conn.fetchval("SELECT id FROM organizations LIMIT 1;")
    broker_id = await conn.fetchval("SELECT id FROM brokers LIMIT 1;")
    test_lead_id = uuid.uuid4()
    test_attr_id = str(uuid.uuid4())

    await conn.execute("""
        INSERT INTO leads (id, organization_id, broker_id, phone, name, status, pipeline_stage, score, score_confidence, preferred_locations, notes)
        VALUES ($1, $2, $3, '+971508887766', 'Action 7 Test Lead', 'pending', 'new', 'warm', 0.8, '{}', '[]'::jsonb);
    """, test_lead_id, org_id, broker_id)

    await conn.execute("""
        INSERT INTO source_attributions (id, organization_id, lead_id, channel, provider, created_at)
        VALUES ($1, $2, $3, 'WEBSITE', 'meta_ads', NOW());
    """, test_attr_id, org_id, test_lead_id)

    # Delete lead and verify attribution lead_id becomes NULL
    await conn.execute("DELETE FROM leads WHERE id = $1;", test_lead_id)
    attr_lead_id = await conn.fetchval("SELECT lead_id FROM source_attributions WHERE id = $1;", test_attr_id)
    assert attr_lead_id is None, "lead_id was not set to NULL upon lead deletion!"
    report["deletion_behavior"] = "PASSED: Lead deleted, SourceAttribution record preserved with lead_id SET NULL."

    await conn.close()
    return report

async def main():
    await setup()
    try:
        run_migration()
        rep = await verify_action7()
        print("\n=== ACTION 7 CONFIRMATION SUMMARY ===")
        print(json.dumps(rep, indent=2))
        with open("scratch/action7_confirmation_results.json", "w") as f:
            json.dump(rep, f, indent=2)
    finally:
        await tear_down()

if __name__ == "__main__":
    asyncio.run(main())

