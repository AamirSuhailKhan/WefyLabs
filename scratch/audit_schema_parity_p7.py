"""
Phase 7 Comprehensive Schema Parity Audit
========================================
Compares the live database schema (in target PostgreSQL schema) against:
1. SQLAlchemy Base.metadata (401 models)
2. Authoritative Alembic head (0047_webhook_event_claims)
3. PostgreSQL extensions (vector, pgcrypto, uuid-ossp)
4. pgvector HNSW index on knowledge_embeddings
5. Webhook deduplication table & constraints
"""
import os
import sys
import json
import asyncio
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api")))

from app.database import engine, Base
import app.models  # Guarantees all 401 ORM models are loaded


async def run_parity_audit(schema_name: str = "phase7_test_disposable") -> dict:
    results = {
        "schema_name": schema_name,
        "expected_model_tables_count": len(Base.metadata.tables),
        "actual_db_tables_count": 0,
        "alembic_version": None,
        "extensions": {},
        "missing_tables": [],
        "extra_tables": [],
        "column_mismatches": [],
        "hnsw_vector_index": False,
        "webhook_claims_table": False,
        "webhook_claims_constraints": [],
        "parity_status": "PENDING"
    }

    async with engine.begin() as conn:
        # Check extensions
        ext_res = await conn.execute(text("SELECT extname, extversion FROM pg_extension"))
        extensions = {row[0]: row[1] for row in ext_res.fetchall()}
        results["extensions"] = extensions
        for req_ext in ["uuid-ossp", "pgcrypto", "vector"]:
            if req_ext not in extensions:
                print(f"[FAIL] Missing extension: {req_ext}")

        # Check tables in schema
        tbl_res = await conn.execute(text(f"""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = '{schema_name}' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))
        db_tables = set(row[0] for row in tbl_res.fetchall())
        results["actual_db_tables_count"] = len(db_tables)

        # Check alembic_version
        if "alembic_version" in db_tables:
            v_res = await conn.execute(text(f"SELECT version_num FROM {schema_name}.alembic_version"))
            results["alembic_version"] = v_res.scalar()

        # Check Base.metadata tables against db_tables
        expected_tables = set(Base.metadata.tables.keys())
        missing = expected_tables - db_tables
        extra = db_tables - expected_tables - {"alembic_version"}
        results["missing_tables"] = sorted(list(missing))
        results["extra_tables"] = sorted(list(extra))

        # Check HNSW index on knowledge_embeddings
        hnsw_res = await conn.execute(text(f"""
            SELECT indexname, indexdef FROM pg_indexes 
            WHERE schemaname = '{schema_name}' AND indexname = 'ix_ke_vector_hnsw'
        """))
        hnsw_row = hnsw_res.fetchone()
        if hnsw_row:
            results["hnsw_vector_index"] = True
            results["hnsw_index_def"] = hnsw_row[1]

        # Check webhook_event_claims uniqueness / constraints
        wc_res = await conn.execute(text(f"""
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            JOIN pg_class cl ON cl.oid = c.conrelid
            WHERE n.nspname = '{schema_name}' AND cl.relname = 'webhook_event_claims'
        """))
        results["webhook_claims_constraints"] = [
            {"constraint_name": row[0], "definition": row[1]} for row in wc_res.fetchall()
        ]
        results["webhook_claims_table"] = "webhook_event_claims" in db_tables

        # Check columns for sample key tables (leads, organizations, webhook_event_claims, knowledge_embeddings)
        audit_sample_tables = ["leads", "organizations", "webhook_event_claims", "knowledge_embeddings", "deals", "users"]
        col_res = await conn.execute(text(f"""
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = '{schema_name}' AND table_name IN ({','.join(f"'{t}'" for t in audit_sample_tables)})
        """))
        cols_by_table = {}
        for r in col_res.fetchall():
            cols_by_table.setdefault(r[0], {})[r[1]] = {"type": r[2], "nullable": r[3]}

        for tname in audit_sample_tables:
            if tname in Base.metadata.tables:
                model_table = Base.metadata.tables[tname]
                db_cols = cols_by_table.get(tname, {})
                for col in model_table.columns:
                    if col.name not in db_cols:
                        results["column_mismatches"].append({
                            "table": tname,
                            "column": col.name,
                            "issue": "missing_in_db"
                        })

        # Overall parity evaluation
        is_clean = (
            len(results["missing_tables"]) == 0 and
            results["actual_db_tables_count"] >= 402 and
            results["alembic_version"] == "0047_webhook_event_claims" and
            results["hnsw_vector_index"] is True and
            results["webhook_claims_table"] is True and
            len(results["column_mismatches"]) == 0
        )

        results["parity_status"] = "CERTIFIED_PARITY" if is_clean else "PARITY_DEFECT"

    await engine.dispose()
    return results


if __name__ == "__main__":
    schema = sys.argv[1] if len(sys.argv) > 1 else "phase7_test_disposable"
    res = asyncio.run(run_parity_audit(schema))
    out_file = os.path.join(os.path.dirname(__file__), "schema_parity_artifact_p7.json")
    with open(out_file, "w") as f:
        json.dump(res, f, indent=2)
    print(f"\nAudit complete. Status: {res['parity_status']}")
    print(f"Schema: {res['schema_name']}")
    print(f"Expected model tables: {res['expected_model_tables_count']}")
    print(f"Actual DB tables: {res['actual_db_tables_count']}")
    print(f"Alembic Version: {res['alembic_version']}")
    print(f"Missing tables: {len(res['missing_tables'])}")
    print(f"Extra tables: {len(res['extra_tables'])}")
    print(f"HNSW Vector Index: {res['hnsw_vector_index']}")
    print(f"Webhook Claims Table: {res['webhook_claims_table']}")
    print(f"Column Mismatches: {len(res['column_mismatches'])}")
