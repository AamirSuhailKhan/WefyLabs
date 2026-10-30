import asyncio
import asyncpg
import uuid

async def run_matrix():
    # Setup test databases
    admin_conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/postgres')
    
    # Ensure isolated test databases
    for db in ['test_db_0048', 'test_db_0049']:
        await admin_conn.execute(f'DROP DATABASE IF EXISTS {db};')
    
    # Create test_db_0048 templated from leadscore (which is at 0048)
    await admin_conn.execute('CREATE DATABASE test_db_0048 WITH TEMPLATE leadscore;')
    # Create test_db_0049 templated from leadscore_pilot (which is at 0049)
    await admin_conn.execute('CREATE DATABASE test_db_0049 WITH TEMPLATE leadscore_pilot;')
    await admin_conn.close()

    print("=== 4-WAY DATABASE COMPATIBILITY MATRIX VERIFICATION ===")

    # Scenario 1: String-based app (simulated by querying with text parameters and joining text columns) against 0048
    conn_0048 = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/test_db_0048')
    try:
        # Check column types in 0048
        attr_lead_type = await conn_0048.fetchval("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'source_attributions' AND column_name = 'lead_id'
        """)
        leads_id_type = await conn_0048.fetchval("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'leads' AND column_name = 'id'
        """)
        print(f"\n[Scenario 1] String-based App vs DB 0048:")
        print(f"  DB 0048 Column types -> source_attributions.lead_id: {attr_lead_type}, leads.id: {leads_id_type}")
        # String query
        res = await conn_0048.fetch("SELECT id, lead_id FROM source_attributions WHERE lead_id = '00000000-0000-0000-0000-000000000001'")
        print(f"  String query on VARCHAR(36) column: COMPATIBLE (returned {len(res)} rows)")
    except Exception as e:
        print(f"  String-based App vs DB 0048 FAILED: {type(e).__name__}: {e}")

    # Scenario 2: Current UUID app against DB 0048
    print(f"\n[Scenario 2] Current UUID-based App vs DB 0048:")
    try:
        test_uuid = uuid.UUID('00000000-0000-0000-0000-000000000001')
        # What happens when asyncpg / SQLAlchemy sends a typed UUID parameter against a VARCHAR(36) column:
        # In asyncpg, passing uuid.UUID sends UUID OID:
        res = await conn_0048.fetch("SELECT id, lead_id FROM source_attributions WHERE lead_id = $1", test_uuid)
        print(f"  UUID param query on VARCHAR column: SUCCESS (Unexpected!)")
    except Exception as e:
        print(f"  UUID param query on VARCHAR column: INCOMPATIBLE ({type(e).__name__}: {e})")

    # What happens when joining leads (UUID) with source_attributions.lead_id (VARCHAR(36)) in 0048:
    try:
        res = await conn_0048.fetch("""
            SELECT s.id, l.id 
            FROM source_attributions s 
            JOIN leads l ON s.lead_id = l.id
        """)
        print(f"  Join leads.id (UUID) = source_attributions.lead_id (VARCHAR): SUCCESS (Unexpected!)")
    except Exception as e:
        print(f"  Join leads.id (UUID) = source_attributions.lead_id (VARCHAR): INCOMPATIBLE ({type(e).__name__}: {e})")

    await conn_0048.close()

    # Scenario 3: String-based app against DB 0049
    conn_0049 = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/test_db_0049')
    try:
        attr_lead_type_49 = await conn_0049.fetchval("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'source_attributions' AND column_name = 'lead_id'
        """)
        print(f"\n[Scenario 3] Legacy String-based App vs DB 0049:")
        print(f"  DB 0049 Column type -> source_attributions.lead_id: {attr_lead_type_49}")
        # Legacy app sends VARCHAR parameter or compares text
        # If legacy code passed raw strings to asyncpg typed as text:
        try:
            res = await conn_0049.fetch("SELECT id, lead_id FROM source_attributions WHERE lead_id = $1::text", '00000000-0000-0000-0000-000000000001')
            print(f"  Text param with text cast query on UUID: SUCCESS")
        except Exception as e:
            print(f"  Text param with text cast query on UUID: INCOMPATIBLE ({type(e).__name__}: {e})")
        # Direct join if legacy table had text:
        try:
            res = await conn_0049.fetch("SELECT s.id FROM source_attributions s WHERE s.lead_id = '00000000-0000-0000-0000-000000000001'::varchar")
            print(f"  Direct comparison UUID = VARCHAR literal: SUCCESS (Unexpected!)")
        except Exception as e:
            print(f"  Direct comparison UUID = VARCHAR literal: INCOMPATIBLE ({type(e).__name__}: {e})")
    except Exception as e:
        print(f"  Legacy String-based App vs DB 0049 error: {type(e).__name__}: {e}")

    # Scenario 4: Current UUID app against DB 0049
    print(f"\n[Scenario 4] Current UUID-based App vs DB 0049:")
    try:
        test_uuid = uuid.UUID('ab5632f5-d9bb-4161-815e-af42bb458fcd')
        # 1. Query with typed UUID
        res = await conn_0049.fetch("SELECT id, lead_id FROM source_attributions WHERE lead_id = $1", test_uuid)
        print(f"  UUID param query on UUID column: COMPATIBLE (returned {len(res)} rows)")
        # 2. Join leads (UUID) with source_attributions.lead_id (UUID)
        res_join = await conn_0049.fetch("""
            SELECT s.id, l.id 
            FROM source_attributions s 
            JOIN leads l ON s.lead_id = l.id
        """)
        print(f"  Join leads.id (UUID) = source_attributions.lead_id (UUID): COMPATIBLE (returned {len(res_join)} rows)")
    except Exception as e:
        print(f"  Current UUID-based App vs DB 0049 FAILED: {type(e).__name__}: {e}")

    await conn_0049.close()

    # Clean up test databases
    admin_conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/postgres')
    for db in ['test_db_0048', 'test_db_0049']:
        await admin_conn.execute(f'DROP DATABASE IF EXISTS {db};')
    await admin_conn.close()
    print("\nCleaned up test_db_0048 and test_db_0049.")

if __name__ == '__main__':
    asyncio.run(run_matrix())

