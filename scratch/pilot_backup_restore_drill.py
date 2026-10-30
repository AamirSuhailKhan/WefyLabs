import asyncio
import asyncpg
import subprocess
import os

async def dr_drill():
    backup_file = "backups/leadscore_pilot_test_backup.dump"
    # Step 1: Dump leadscore_pilot
    dump_cmd = [
        "docker", "exec", "leadscore_postgres",
        "pg_dump", "-U", "postgres", "-d", "leadscore_pilot",
        "-F", "c", "-b", "-f", "/tmp/pilot_backup.dump"
    ]
    res1 = subprocess.run(dump_cmd, capture_output=True, text=True)
    print("1. pg_dump returncode:", res1.returncode)
    assert res1.returncode == 0, f"pg_dump failed: {res1.stderr}"
    
    # Step 2: Create restore verification target DB
    sys_conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/postgres")
    await sys_conn.execute("DROP DATABASE IF EXISTS leadscore_pilot_restore_verify;")
    await sys_conn.execute("CREATE DATABASE leadscore_pilot_restore_verify;")
    print("2. Created target DB leadscore_pilot_restore_verify")
    await sys_conn.close()
    
    # Step 3: Execute pg_restore into leadscore_pilot_restore_verify
    restore_cmd = [
        "docker", "exec", "leadscore_postgres",
        "pg_restore", "-U", "postgres", "-d", "leadscore_pilot_restore_verify",
        "--clean", "--if-exists", "--no-owner", "--no-privileges", "--single-transaction",
        "/tmp/pilot_backup.dump"
    ]
    res2 = subprocess.run(restore_cmd, capture_output=True, text=True)
    print("3. pg_restore returncode:", res2.returncode)
    assert res2.returncode == 0, f"pg_restore failed: {res2.stderr}"
    
    # Step 4: Verify restored database
    verify_conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/leadscore_pilot_restore_verify")
    rev = await verify_conn.fetchval("SELECT version_num FROM alembic_version;")
    tables = await verify_conn.fetchval("SELECT count(table_name) FROM information_schema.tables WHERE table_schema = 'public';")
    print(f"4. Verified restored DB: Revision={rev}, Tables={tables}")
    assert rev == "0049_source_attribution_uuid_parity", f"Unexpected revision: {rev}"
    assert tables == 411, f"Unexpected table count: {tables}"
    await verify_conn.close()
    
    # Step 5: Clean up verification DB
    sys_conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/postgres")
    await sys_conn.execute("DROP DATABASE leadscore_pilot_restore_verify;")
    print("5. Dropped leadscore_pilot_restore_verify after successful verification.")
    await sys_conn.close()
    print("--- PILOT BACKUP & RESTORE DRILL PASSED 100% ---")

if __name__ == "__main__":
    asyncio.run(dr_drill())

