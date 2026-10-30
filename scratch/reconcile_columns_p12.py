import os
import sys
import json
import asyncio
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api")))

from app.database import engine, Base
import app.models

async def reconcile_columns(schema_name: str = "phase9_fresh_disposable"):
    async with engine.begin() as conn:
        # 1. Total tables in Base.metadata
        model_tables = set(Base.metadata.tables.keys())
        print(f"Total tables in Base.metadata: {len(model_tables)}")

        # 2. Total tables in DB schema
        res = await conn.execute(text(f"""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = '{schema_name}' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))
        db_tables = set(row[0] for row in res.fetchall())
        print(f"Total tables in DB schema '{schema_name}': {len(db_tables)}")
        print(f"Difference: db_tables - model_tables = {db_tables - model_tables}")
        print(f"Difference: model_tables - db_tables = {model_tables - db_tables}")

        # 3. Columns per table
        res_cols = await conn.execute(text(f"""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = '{schema_name}'
            ORDER BY table_name, ordinal_position
        """))
        db_cols_by_table = {}
        for r in res_cols.fetchall():
            db_cols_by_table.setdefault(r[0], []).append(r[1])

        # Separate alembic_version
        alembic_cols = db_cols_by_table.get("alembic_version", [])
        print(f"alembic_version columns: {alembic_cols} (count: {len(alembic_cols)})")

        # Sum of columns in 410 application tables in DB
        app_db_cols_count = sum(len(cols) for t, cols in db_cols_by_table.items() if t != "alembic_version")
        total_db_cols = sum(len(cols) for cols in db_cols_by_table.values())
        print(f"Total columns in DB across all tables: {total_db_cols}")
        print(f"Total columns in DB across 410 application tables: {app_db_cols_count}")

        # Sum of columns in Base.metadata
        total_model_cols = sum(len(table.columns) for table in Base.metadata.tables.values())
        print(f"Total columns in Base.metadata across {len(model_tables)} tables: {total_model_cols}")

        # Find per-table differences between Base.metadata and DB
        diffs = []
        for tname in sorted(list(model_tables)):
            model_col_names = [c.name for c in Base.metadata.tables[tname].columns]
            db_col_names = db_cols_by_table.get(tname, [])
            
            missing_in_db = set(model_col_names) - set(db_col_names)
            extra_in_db = set(db_col_names) - set(model_col_names)
            
            if missing_in_db or extra_in_db:
                diffs.append({
                    "table": tname,
                    "model_count": len(model_col_names),
                    "db_count": len(db_col_names),
                    "missing_in_db": list(missing_in_db),
                    "extra_in_db": list(extra_in_db)
                })

        print(f"\nTables with differences between Model and DB: {len(diffs)}")
        for d in diffs:
            print(f"  Table '{d['table']}': model={d['model_count']}, db={d['db_count']}")
            if d['missing_in_db']:
                print(f"    Missing in DB: {d['missing_in_db']}")
            if d['extra_in_db']:
                print(f"    Extra in DB: {d['extra_in_db']}")

if __name__ == "__main__":
    asyncio.run(reconcile_columns())
