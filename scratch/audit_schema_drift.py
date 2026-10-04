import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv('apps/api/.env')
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text

async def run_schema_drift():
    url = os.environ.get('DATABASE_URL')
    engine = create_async_engine(url, poolclass=NullPool)
    
    async with engine.connect() as conn:
        print("=== ALL PUBLIC TABLES MATCHING KEYWORDS ===")
        res = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        all_tables = [r[0] for r in res.fetchall()]
        print(f"Total public tables in DB: {len(all_tables)}")
        
        keywords = ['lead', 'qualif', 'consent', 'timeline', 'comm', 'messag', 'shortlist', 'deal', 'convers', 'agent', 'event']
        matched_tables = [t for t in all_tables if any(k in t.lower() for k in keywords)]
        print(f"Matched tables ({len(matched_tables)}):")
        for mt in matched_tables:
            print(f"  - {mt}")

        print("\n=== COLUMN INSPECTION FOR RELEVANT TABLES ===")
        target_tables = [
            'leads', 'lead_profiles', 'lead_scores', 'conversations', 'messages', 
            'whatsapp_messages', 'email_logs', 'deals', 'deals_pipeline',
            'properties', 'property_matches', 'buyer_preferences', 'qualifications'
        ]
        
        for t in target_tables:
            if t in all_tables:
                print(f"\n--- Columns in {t} ---")
                col_res = await conn.execute(text(f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = '{t}'
                    ORDER BY ordinal_position
                """))
                for c in col_res.fetchall():
                    print(f"  {c[0]} ({c[1]}, nullable={c[2]})")
            else:
                print(f"\n--- {t} NOT IN DATABASE ---")

if __name__ == '__main__':
    asyncio.run(run_schema_drift())
