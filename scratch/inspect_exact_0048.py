import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/leadscore')
    
    # 1. source_attributions
    cols_sa = await conn.fetch("""
        SELECT column_name, data_type, udt_name, is_nullable 
        FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'source_attributions'
        ORDER BY ordinal_position
    """)
    print("=== source_attributions columns in leadscore (0048) ===")
    for c in cols_sa:
        print(f"  {c['column_name']}: {c['data_type']} ({c['udt_name']}), nullable={c['is_nullable']}")
    
    # 2. leads
    cols_l = await conn.fetch("""
        SELECT column_name, data_type, udt_name, is_nullable 
        FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'leads' AND column_name IN ('id', 'organization_id')
    """)
    print("\n=== leads columns in leadscore (0048) ===")
    for c in cols_l:
        print(f"  {c['column_name']}: {c['data_type']} ({c['udt_name']}), nullable={c['is_nullable']}")

    # 3. organizations
    cols_o = await conn.fetch("""
        SELECT column_name, data_type, udt_name, is_nullable 
        FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'organizations' AND column_name = 'id'
    """)
    print("\n=== organizations columns in leadscore (0048) ===")
    for c in cols_o:
        print(f"  {c['column_name']}: {c['data_type']} ({c['udt_name']}), nullable={c['is_nullable']}")

    # 4. foreign keys on source_attributions
    fks = await conn.fetch("""
        SELECT tc.constraint_name, kcu.column_name, ccu.table_name AS foreign_table, ccu.column_name AS foreign_col
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
        WHERE tc.table_name = 'source_attributions' AND tc.constraint_type = 'FOREIGN KEY'
    """)
    print("\n=== foreign keys on source_attributions in leadscore (0048) ===")
    for fk in fks:
        print(f"  {fk['constraint_name']}: {fk['column_name']} -> {fk['foreign_table']}.{fk['foreign_col']}")

    # 5. actual rows in source_attributions
    rows = await conn.fetch("SELECT * FROM source_attributions")
    print(f"\n=== source_attributions actual data ({len(rows)} rows) ===")
    for r in rows:
        print(f"  {dict(r)}")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())

