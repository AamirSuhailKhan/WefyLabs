"""
Scratch Script: Test SourceAttribution Schema Migration on Isolated Database
Database: leadscore_test_acceptance (NEVER live leadscore)
Driver: asyncpg
Tests:
1. Ensure baseline VARCHAR(36) state
2. Safe Upgrade:
   - Convert organization_id to UUID with FK organizations(id) ON DELETE CASCADE
   - Convert lead_id to UUID with FK leads(id) ON DELETE SET NULL (nullable)
3. Referential Integrity Test:
   - Insert valid record referencing existing lead and org -> SUCCESS
   - Insert invalid record referencing nonexistent lead -> FAILS (Foreign Key Violation)
   - Delete test lead -> verifies lead_id in attribution becomes NULL
   - Clean up test record
4. Safe Rollback:
   - Drop FK constraints
   - Convert back to VARCHAR(36)
   - Restore NOT NULL on lead_id
5. Verification of clean rollback
"""
import asyncio
import asyncpg
import uuid

DB_URL = "postgresql://postgres:postgres@127.0.0.1:5432/leadscore_test_acceptance"

async def run_test():
    conn = await asyncpg.connect(DB_URL)

    # Reset to baseline first if necessary
    reset_sql = """
    ALTER TABLE source_attributions 
        DROP CONSTRAINT IF EXISTS fk_source_attributions_lead_id,
        DROP CONSTRAINT IF EXISTS fk_source_attributions_organization_id;

    ALTER TABLE source_attributions 
        ALTER COLUMN lead_id TYPE character varying(36) USING lead_id::text,
        ALTER COLUMN organization_id TYPE character varying(36) USING organization_id::text;

    ALTER TABLE source_attributions ALTER COLUMN lead_id SET NOT NULL;
    """
    await conn.execute(reset_sql)

    print("[1] Baseline check on leadscore_test_acceptance...")
    cols = await conn.fetch("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'source_attributions' AND column_name IN ('lead_id', 'organization_id') ORDER BY column_name;")
    baseline_state = [(r['column_name'], r['data_type'], r['is_nullable']) for r in cols]
    print("Baseline columns:", baseline_state)
    assert baseline_state == [('lead_id', 'character varying', 'NO'), ('organization_id', 'character varying', 'NO')]

    print("\n[2] Executing Upgrade Migration...")
    upgrade_sql = """
    ALTER TABLE source_attributions ALTER COLUMN lead_id DROP NOT NULL;
    
    ALTER TABLE source_attributions 
        ALTER COLUMN organization_id TYPE uuid USING organization_id::uuid,
        ALTER COLUMN lead_id TYPE uuid USING lead_id::uuid;
        
    ALTER TABLE source_attributions
        ADD CONSTRAINT fk_source_attributions_organization_id 
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;

    ALTER TABLE source_attributions
        ADD CONSTRAINT fk_source_attributions_lead_id 
        FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL;
    """
    await conn.execute(upgrade_sql)
    print("Upgrade migration executed successfully.")

    print("\n[3] Introspecting migrated columns and constraints...")
    migrated_cols = await conn.fetch("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'source_attributions' AND column_name IN ('lead_id', 'organization_id') ORDER BY column_name;")
    print("Migrated columns:", [(r['column_name'], r['data_type'], r['is_nullable']) for r in migrated_cols])
    for r in migrated_cols:
        assert r['data_type'] in ("USER-DEFINED", "uuid"), f"Expected uuid type, got {r['data_type']}"

    fks_rows = await conn.fetch("""
        SELECT conname, confdeltype 
        FROM pg_constraint 
        WHERE conrelid = 'source_attributions'::regclass 
        AND conname IN ('fk_source_attributions_organization_id', 'fk_source_attributions_lead_id');
    """)
    fks = {r['conname']: (r['confdeltype'].decode('ascii') if isinstance(r['confdeltype'], bytes) else str(r['confdeltype'])) for r in fks_rows}
    print("FK Constraints found:", fks)
    assert 'fk_source_attributions_organization_id' in fks, "Missing org FK"
    assert 'fk_source_attributions_lead_id' in fks, "Missing lead FK"
    assert fks['fk_source_attributions_organization_id'] == 'c', f"Expected CASCADE ('c'), got {fks['fk_source_attributions_organization_id']}"
    assert fks['fk_source_attributions_lead_id'] == 'n', f"Expected SET NULL ('n'), got {fks['fk_source_attributions_lead_id']}"
    print("Referential integrity constraints correctly configured.")

    print("\n[4] Testing Referential Integrity in practice...")
    org_id = await conn.fetchval("SELECT id FROM organizations LIMIT 1;")
    broker_id = await conn.fetchval("SELECT id FROM brokers LIMIT 1;")

    test_lead_id = uuid.uuid4()
    test_attr_id = str(uuid.uuid4())

    # Create temporary test lead
    await conn.execute("""
        INSERT INTO leads (id, organization_id, broker_id, phone, name, status, pipeline_stage, score, score_confidence, preferred_locations, notes)
        VALUES ($1, $2, $3, '+971509999999', 'Test Temp Lead', 'pending', 'new', 'warm', 0.8, '{}', '[]'::jsonb);
    """, test_lead_id, org_id, broker_id)

    # Insert test attribution pointing to this lead
    await conn.execute("""
        INSERT INTO source_attributions (id, organization_id, lead_id, channel, provider, created_at)
        VALUES ($1, $2, $3, 'WEBSITE', 'meta_ads', NOW());
    """, test_attr_id, org_id, test_lead_id)
    print("Inserted test lead and test attribution successfully.")

    # Try inserting attribution pointing to NONEXISTENT lead (must fail)
    fake_lead_id = uuid.uuid4()
    fake_attr_id = str(uuid.uuid4())
    failed_as_expected = False
    try:
        await conn.execute("""
            INSERT INTO source_attributions (id, organization_id, lead_id, channel, provider, created_at)
            VALUES ($1, $2, $3, 'WEBSITE', 'meta_ads', NOW());
        """, fake_attr_id, org_id, fake_lead_id)
    except asyncpg.ForeignKeyViolationError:
        failed_as_expected = True
    assert failed_as_expected, "Inserting attribution with invalid lead_id should fail with ForeignKeyViolationError!"
    print("Referential check PASSED: Nonexistent lead was rejected by foreign key.")

    # Delete test lead -> verify test attribution lead_id becomes NULL (SET NULL policy)
    await conn.execute("DELETE FROM leads WHERE id = $1;", test_lead_id)
    attr_lead_id = await conn.fetchval("SELECT lead_id FROM source_attributions WHERE id = $1;", test_attr_id)
    assert attr_lead_id is None, f"Expected lead_id to be SET NULL upon lead deletion, but got {attr_lead_id}"
    print("SET NULL policy PASSED: Lead deletion preserved attribution record with lead_id set to NULL.")

    # Clean up test attribution
    await conn.execute("DELETE FROM source_attributions WHERE id = $1;", test_attr_id)

    print("\n[5] Testing Rollback Migration...")
    rollback_sql = """
    ALTER TABLE source_attributions 
        DROP CONSTRAINT IF EXISTS fk_source_attributions_lead_id,
        DROP CONSTRAINT IF EXISTS fk_source_attributions_organization_id;

    ALTER TABLE source_attributions 
        ALTER COLUMN lead_id TYPE character varying(36) USING lead_id::text,
        ALTER COLUMN organization_id TYPE character varying(36) USING organization_id::text;

    ALTER TABLE source_attributions ALTER COLUMN lead_id SET NOT NULL;
    """
    await conn.execute(rollback_sql)
    print("Rollback executed successfully.")

    print("\n[6] Introspecting rolled-back schema...")
    reverted_cols = await conn.fetch("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'source_attributions' AND column_name IN ('lead_id', 'organization_id') ORDER BY column_name;")
    reverted_state = [(r['column_name'], r['data_type'], r['is_nullable']) for r in reverted_cols]
    print("Reverted columns:", reverted_state)
    assert reverted_state == baseline_state, "Reverted columns do not match baseline!"
    print("Rollback test SUCCESSFUL! Isolated DB restored exactly to baseline.")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(run_test())
