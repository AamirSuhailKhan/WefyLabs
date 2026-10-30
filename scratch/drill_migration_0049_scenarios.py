import asyncio
import asyncpg
import uuid

async def test_scenarios():
    conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/postgres')
    await conn.execute('DROP DATABASE IF EXISTS phase13_migration_drill;')
    await conn.execute('CREATE DATABASE phase13_migration_drill WITH TEMPLATE leadscore;')
    await conn.close()
    print('Created phase13_migration_drill from leadscore (0048)')

    drill_conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/phase13_migration_drill')
    
    # 1. Test malformed string behavior during cast to UUID
    print('--- 1. Testing Malformed String Cast ---')
    try:
        await drill_conn.execute("""
            INSERT INTO source_attributions (id, organization_id, lead_id, created_at)
            VALUES ('test-bad-uuid', 'not-a-valid-uuid', 'also-not-uuid', NOW());
        """)
        print('Inserted malformed string row')
        try:
            await drill_conn.execute("""
                ALTER TABLE source_attributions 
                ALTER COLUMN organization_id TYPE uuid USING organization_id::uuid;
            """)
            print('Cast with bad UUID: SUCCESS (Unexpected!)')
        except Exception as e:
            print('Cast with bad UUID FAILED as expected:', type(e).__name__, str(e).strip()[:100])
        # Clean up bad row
        await drill_conn.execute("DELETE FROM source_attributions WHERE id = 'test-bad-uuid';")
    except Exception as e:
        print('Error in malformed test:', e)

    # 2. Test upgrade to 0049
    print('\n--- 2. Testing Upgrade to 0049 ---')
    await drill_conn.execute("ALTER TABLE source_attributions ALTER COLUMN lead_id DROP NOT NULL;")
    await drill_conn.execute("""
        ALTER TABLE source_attributions 
        ALTER COLUMN organization_id TYPE uuid USING organization_id::uuid, 
        ALTER COLUMN lead_id TYPE uuid USING lead_id::uuid;
    """)
    await drill_conn.execute("""
        ALTER TABLE source_attributions 
        ADD CONSTRAINT fk_source_attributions_organization_id 
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
    """)
    await drill_conn.execute("""
        ALTER TABLE source_attributions 
        ADD CONSTRAINT fk_source_attributions_lead_id 
        FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL;
    """)
    await drill_conn.execute("UPDATE alembic_version SET version_num = '0049_source_attribution_uuid_parity';")
    print('Upgrade to 0049 completed successfully!')

    # Check row count
    c = await drill_conn.fetchval('SELECT count(*) FROM source_attributions')
    print('Attribution rows after upgrade:', c)

    # 3. Test Lead Deletion -> ON DELETE SET NULL
    print('\n--- 3. Testing Lead Deletion & SET NULL ---')
    row = await drill_conn.fetchrow('SELECT id, organization_id, lead_id FROM source_attributions WHERE lead_id IS NOT NULL LIMIT 1')
    target_attr_id = row['id']
    target_lead_id = row['lead_id']
    print(f'Target attribution {target_attr_id} linked to lead {target_lead_id}')

    # Delete the lead
    await drill_conn.execute('DELETE FROM leads WHERE id = $1', target_lead_id)
    print(f'Deleted lead {target_lead_id}')

    # Verify attribution still exists and lead_id is NULL
    attr_after = await drill_conn.fetchrow('SELECT id, lead_id FROM source_attributions WHERE id = $1', target_attr_id)
    print(f'Attribution {attr_after["id"]} after lead deletion: lead_id = {attr_after["lead_id"]}')
    assert attr_after['lead_id'] is None, 'lead_id should be NULL!'

    # 4. Test Downgrade attempt when lead_id IS NULL
    print('\n--- 4. Testing Downgrade Attempt with NULL lead_id ---')
    try:
        await drill_conn.execute("""
            ALTER TABLE source_attributions 
            DROP CONSTRAINT IF EXISTS fk_source_attributions_lead_id, 
            DROP CONSTRAINT IF EXISTS fk_source_attributions_organization_id;
        """)
        await drill_conn.execute("""
            ALTER TABLE source_attributions 
            ALTER COLUMN lead_id TYPE character varying(36) USING lead_id::text, 
            ALTER COLUMN organization_id TYPE character varying(36) USING organization_id::text;
        """)
        await drill_conn.execute("ALTER TABLE source_attributions ALTER COLUMN lead_id SET NOT NULL;")
        print('Downgrade succeeded (UNEXPECTED!)')
    except Exception as e:
        print('Downgrade FAILED as expected on SET NOT NULL:', type(e).__name__, str(e).strip()[:120])

    # 5. Evaluate Strategy 1: Pre-downgrade Safety Guard (Fail-Closed)
    print('\n--- 5. Evaluating Strategy 1: Pre-downgrade Safety Guard (Fail-Closed) ---')
    null_count = await drill_conn.fetchval('SELECT count(*) FROM source_attributions WHERE lead_id IS NULL;')
    print(f'Pre-downgrade check: Found {null_count} orphaned/unlinked attribution records with lead_id IS NULL.')
    if null_count > 0:
        print('Strategy 1 Result: Downgrade BLOCKED safely with actionable pre-flight check error.')

    # 6. Evaluate Strategy 4: Tombstone Lead Analysis
    print('\n--- 6. Evaluating Strategy 4: Tombstone Lead Analysis ---')
    # If a tombstone lead is created:
    # What are the required fields for a Lead?
    lead_cols = await drill_conn.fetch("""
        SELECT column_name, is_nullable, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'leads' AND is_nullable = 'NO' AND column_default IS NULL;
    """)
    print('Required NOT-NULL columns in leads with no default:', [r['column_name'] for r in lead_cols])

    # 7. Evaluate Strategy 2: Forward-Recovery Migration
    print('\n--- 7. Evaluating Strategy 2: Forward-Recovery Migration ---')
    print('Forward recovery principle: Instead of rolling back schema to non-nullable VARCHAR,')
    print('any rollback of application code can be accommodated while keeping 0049 schema intact,')
    print('OR if 0048 schema is required, migration 0050 relaxes the NOT NULL constraint on 0048.')

    await drill_conn.close()
    conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/postgres')
    await conn.execute('DROP DATABASE IF EXISTS phase13_migration_drill;')
    await conn.close()
    print('Cleaned up phase13_migration_drill')

if __name__ == '__main__':
    asyncio.run(test_scenarios())

