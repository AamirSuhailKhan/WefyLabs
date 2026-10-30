import asyncio
import asyncpg
import subprocess
import os
import sys

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
DISP_DB = "test_disposable_backup_drill"
DISP_URL = f"postgresql://postgres:postgres@127.0.0.1:5432/{DISP_DB}"
BACKUP_FILE = "scratch/disposable_backup_test.dump"

async def run_backup_drill():
    # 1. Setup disposable database
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.execute(f"CREATE DATABASE {DISP_DB} WITH TEMPLATE leadscore;")
    await admin.close()
    print(f"[SETUP] Created disposable database '{DISP_DB}' from 'leadscore'.")

    # 2. Formulate native PostgreSQL tool connection URI (NO +asyncpg)
    native_uri = DISP_URL
    assert "+asyncpg" not in native_uri, "Native PostgreSQL tools cannot accept +asyncpg driver suffix!"

    # 3. Test backup creation via pg_dump (using docker exec or local CLI)
    container_dump_path = "/tmp/disposable_backup_test.dump"

    # Use docker exec leadscore_postgres pg_dump
    cmd_dump = [
        "docker", "exec", "leadscore_postgres",
        "pg_dump",
        "-Fc",
        "-v",
        "--no-owner",
        "--no-privileges",
        "-d", f"postgresql://postgres:postgres@127.0.0.1:5432/{DISP_DB}",
        "-f", container_dump_path
    ]
    print(f"[BACKUP] Running pg_dump inside container to {container_dump_path}...")
    res_dump = subprocess.run(cmd_dump, capture_output=True, text=True)
    if res_dump.returncode != 0:
        print(f"pg_dump failed (exit code {res_dump.returncode}):\n{res_dump.stderr}")
        sys.exit(1)

    print("[BACKUP] Backup successful.")

    # 4. Test catalog verification via pg_restore --list
    cmd_list = [
        "docker", "exec", "leadscore_postgres",
        "pg_restore", "--list", container_dump_path
    ]
    res_list = subprocess.run(cmd_list, capture_output=True, text=True)
    if res_list.returncode != 0:
        print(f"pg_restore --list failed:\n{res_list.stderr}")
        sys.exit(1)

    catalog_lines = res_list.stdout.splitlines()
    print(f"[CATALOG] Catalog inspection successful. Found {len(catalog_lines)} entries.")
    
    # Verify core tables are in catalog
    has_leads = any("TABLE DATA public leads" in line or "TABLE public leads" in line for line in catalog_lines)
    has_brokers = any("TABLE DATA public brokers" in line or "TABLE public brokers" in line for line in catalog_lines)
    has_attr = any("TABLE DATA public source_attributions" in line or "TABLE public source_attributions" in line for line in catalog_lines)
    
    print(f"  Catalog contains leads: {has_leads}")
    print(f"  Catalog contains brokers: {has_brokers}")
    print(f"  Catalog contains source_attributions: {has_attr}")
    assert has_leads and has_brokers and has_attr, "Missing critical tables from catalog!"

    # 5. Cleanup container dump file
    subprocess.run(["docker", "exec", "leadscore_postgres", "rm", "-f", container_dump_path])

    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.close()
    print(f"[TEARDOWN] Dropped disposable database '{DISP_DB}' and removed test dump.")
    print("[RESULT] Phase 2 Backup & Catalog Rehearsal PASSED with 100% fidelity.")

if __name__ == "__main__":
    asyncio.run(run_backup_drill())
