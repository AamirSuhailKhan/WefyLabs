import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api")))

from sqlalchemy import create_engine, text
from app.database import Base
import app.models

def main():
    engine = create_engine("postgresql://postgres:postgres@127.0.0.1:5432/leadscore")
    with engine.connect() as conn:
        res = conn.execute(text("""
            SELECT table_name, column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public'
        """)).fetchall()
        db_cols = set((r[0], r[1]) for r in res)
        
        missing = []
        for table_name, table in Base.metadata.tables.items():
            for col in table.columns:
                if (table_name, col.name) not in db_cols:
                    missing.append((table_name, col.name, str(col.type)))
                    
        print(f"Total ORM tables: {len(Base.metadata.tables)}")
        print(f"Missing columns in public: {len(missing)}")
        for m in missing[:30]:
            print(f"  MISSING: {m[0]}.{m[1]} ({m[2]})")

if __name__ == "__main__":
    main()
