import os
import asyncio
from dotenv import load_dotenv
import asyncpg

load_dotenv("apps/api/.env", override=False)
db_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

async def inspect():
    conn = await asyncpg.connect(db_url)
    try:
        rev = await conn.fetchval("SELECT version_num FROM alembic_version")
        print(f"alembic_version in public schema: {rev}")
        
        cols = await conn.fetch("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'source_attributions'
            ORDER BY ordinal_position
        """)
        print("\npublic.source_attributions columns:")
        for c in cols:
            print(f"  {c['column_name']}: {c['data_type']} (nullable={c['is_nullable']})")

        fks = await conn.fetch("""
            SELECT tc.constraint_name, kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name 
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name='source_attributions' AND tc.table_schema='public';
        """)
        print(f"\npublic.source_attributions FKs: {len(fks)}")
        for fk in fks:
            print(f"  {fk['constraint_name']}: {fk['column_name']} -> {fk['foreign_table_name']}({fk['foreign_column_name']})")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect())

