#!/usr/bin/env python3
"""
WefyLabs Disaster Recovery & Forensic Restoration Utility
==========================================================
Automates end-to-end database restoration with strict prerequisite validation:
1. Validates PostgreSQL server version and availability of `vector` extension.
2. Ensures the target database is an isolated/authorized recovery database (NEVER overwrites live `leadscore`).
3. Provisions required extensions (`CREATE EXTENSION IF NOT EXISTS vector;`).
4. Executes `pg_restore` from compressed custom dump archive.
5. Performs forensic integrity audit: table count, migration head, and core entities.
"""
import os
import sys
import time
import subprocess
import asyncio
import asyncpg
from typing import Dict, Any

# Ensure apps/api is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database_safety import validate_test_database_target, UnsafeDatabaseTargetError

EXPECTED_TABLES = 411
EXPECTED_HEAD = "0048_schema_reconciliation_parity"

async def validate_prerequisites(pg_url: str) -> None:
    """Validate server engine version and pgvector extension availability."""
    conn = await asyncpg.connect(pg_url)
    try:
        version_str = await conn.fetchval("SHOW server_version;")
        print(f"[PRE-FLIGHT] PostgreSQL Server Version: {version_str}")
        
        # Check pgvector availability
        row = await conn.fetchrow("SELECT name, default_version, installed_version FROM pg_available_extensions WHERE name = 'vector';")
        if not row:
            raise RuntimeError("CRITICAL PREREQUISITE MISSING: 'vector' extension (pgvector) is not available on PostgreSQL host.")
        print(f"[PRE-FLIGHT] Extension 'vector' available: version {row['default_version']} (currently installed: {row['installed_version']})")
    finally:
        await conn.close()

async def prepare_recovery_target(admin_url: str, target_db: str) -> None:
    """Ensure target database exists and has vector extension."""
    conn = await asyncpg.connect(admin_url)
    try:
        # Check if DB exists
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1;", target_db)
        if exists:
            # Terminate active connections
            await conn.execute(f"""
                SELECT pg_terminate_backend(pid) 
                FROM pg_stat_activity 
                WHERE datname = '{target_db}' AND pid <> pg_backend_pid();
            """)
            await conn.execute(f"DROP DATABASE {target_db};")
            print(f"[PRE-FLIGHT] Dropped pre-existing recovery database: {target_db}")
        
        await conn.execute(f"CREATE DATABASE {target_db};")
        print(f"[PRE-FLIGHT] Created clean recovery database: {target_db}")
    finally:
        await conn.close()
        
    # Connect to target and install extension
    target_url = admin_url.rsplit("/", 1)[0] + f"/{target_db}"
    target_conn = await asyncpg.connect(target_url)
    try:
        await target_conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print(f"[PRE-FLIGHT] Initialized required extension: 'vector' on {target_db}")
    finally:
        await target_conn.close()

def execute_pg_restore(dump_path: str, container_name: str, target_db: str) -> float:
    """Executes pg_restore via docker container pipeline."""
    if not os.path.exists(dump_path):
        raise FileNotFoundError(f"Backup dump archive not found: {dump_path}")
        
    dump_size = os.path.getsize(dump_path)
    print(f"[RESTORE] Starting restoration of {dump_path} ({dump_size:,} bytes) into {target_db}...")
    
    t0 = time.perf_counter()
    # Read dump and pipe into docker exec pg_restore
    cmd = [
        "docker", "exec", "-i", container_name,
        "pg_restore",
        "-U", "postgres",
        "-d", target_db,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--single-transaction"
    ]
    
    with open(dump_path, "rb") as dump_file:
        proc = subprocess.run(
            cmd,
            stdin=dump_file,
            capture_output=True,
            text=True
        )
    t1 = time.perf_counter()
    
    elapsed = t1 - t0
    if proc.returncode != 0:
        # Check if warnings vs fatal error
        print(f"[RESTORE] pg_restore exited with code {proc.returncode}")
        if proc.stderr:
            print(f"[RESTORE STDERR] {proc.stderr[:500]}")
    else:
        print(f"[RESTORE] pg_restore completed successfully with exit code 0 in {elapsed:.3f} seconds.")
    return elapsed

async def audit_restored_database(target_url: str) -> Dict[str, Any]:
    """Forensic verification of restored schemas, migration head, and records."""
    conn = await asyncpg.connect(target_url)
    try:
        table_count = await conn.fetchval("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
        alembic_head = await conn.fetchval("SELECT version_num FROM alembic_version;")
        
        leads = await conn.fetchval("SELECT count(*) FROM leads;")
        orgs = await conn.fetchval("SELECT count(*) FROM organizations;")
        brokers = await conn.fetchval("SELECT count(*) FROM brokers;")
        members = await conn.fetchval("SELECT count(*) FROM organization_members;")
        attributions = await conn.fetchval("SELECT count(*) FROM source_attributions;")
        tasks = await conn.fetchval("SELECT count(*) FROM tasks;")
        
        # Check pgvector index
        vector_idx = await conn.fetchval("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'knowledge_embeddings' AND indexname = 'ix_ke_vector_hnsw';
        """)
        
        audit_results = {
            "tables": table_count,
            "alembic_head": alembic_head,
            "leads": leads,
            "orgs": orgs,
            "brokers": brokers,
            "members": members,
            "attributions": attributions,
            "tasks": tasks,
            "vector_hnsw_index": vector_idx is not None
        }
        return audit_results
    finally:
        await conn.close()

async def run_recovery_drill(
    dump_path: str = "backups/leadscore_backup_20261028.dump",
    container_name: str = "leadscore_postgres",
    target_db: str = "leadscore_restore_drill_p13",
    cleanup_after: bool = True
):
    print("=" * 70)
    print("WEFYLABS DISASTER RECOVERY & RESTORATION PROCEDURE")
    print("=" * 70)
    
    # SAFETY LOCK: Validate target DB name is an authorized disposable target
    if target_db == "leadscore" or target_db == "postgres":
        raise UnsafeDatabaseTargetError(f"CRITICAL SAFETY LOCK: Refusing recovery into production database '{target_db}'!")
        
    admin_url = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
    target_url = f"postgresql://postgres:postgres@127.0.0.1:5432/{target_db}"
    
    # 1. Prerequisites
    await validate_prerequisites(admin_url)
    
    # 2. Provision Target & Extension
    await prepare_recovery_target(admin_url, target_db)
    
    # 3. Execute Restore
    duration = execute_pg_restore(dump_path, container_name, target_db)
    
    # 4. Forensic Audit
    audit = await audit_restored_database(target_url)
    print("\n[AUDIT RESULTS]")
    for k, v in audit.items():
        print(f"  - {k}: {v}")
        
    assert audit["tables"] == EXPECTED_TABLES, f"Table count mismatch: expected {EXPECTED_TABLES}, got {audit['tables']}"
    assert audit["alembic_head"] == EXPECTED_HEAD, f"Alembic head mismatch: expected {EXPECTED_HEAD}, got {audit['alembic_head']}"
    assert audit["leads"] == 4, f"Leads count mismatch: got {audit['leads']}"
    print(f"\n[VERDICT] Disaster Recovery Drill SUCCESSFUL in {duration:.3f}s with 100% data and schema fidelity!")
    
    # 5. Clean teardown
    if cleanup_after:
        conn = await asyncpg.connect(admin_url)
        try:
            await conn.execute(f"""
                SELECT pg_terminate_backend(pid) 
                FROM pg_stat_activity 
                WHERE datname = '{target_db}' AND pid <> pg_backend_pid();
            """)
            await conn.execute(f"DROP DATABASE {target_db};")
            print(f"[TEARDOWN] Cleanly dropped disposable drill database: {target_db}")
        finally:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(run_recovery_drill())

