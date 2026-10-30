import asyncio
import asyncpg
import subprocess
import os
import sys

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
SOURCE_DB = "test_disposable_source_for_restore"
RESTORED_DB = "test_disposable_restored_db"
DUMP_PATH = "/tmp/rehearsal_full_backup.dump"

async def run_rehearsal():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {SOURCE_DB};")
    await admin.execute(f"DROP DATABASE IF EXISTS {RESTORED_DB};")
    await admin.execute(f"CREATE DATABASE {SOURCE_DB} WITH TEMPLATE leadscore;")
    await admin.execute(f"CREATE DATABASE {RESTORED_DB};")
    await admin.close()
    print(f"[SETUP] Created '{SOURCE_DB}' and '{RESTORED_DB}'.")

    # Step 1: Execute pg_dump inside container
    cmd_dump = [
        "docker", "exec", "leadscore_postgres",
        "pg_dump", "-Fc", "-v", "--no-owner", "--no-privileges",
        "-d", f"postgresql://postgres:postgres@127.0.0.1:5432/{SOURCE_DB}",
        "-f", DUMP_PATH
    ]
    res_dump = subprocess.run(cmd_dump, capture_output=True, text=True)
    assert res_dump.returncode == 0, f"pg_dump failed: {res_dump.stderr}"
    print("[BACKUP] Binary dump created successfully.")

    # Step 2: Simulate post-backup write on SOURCE_DB
    c_source = await asyncpg.connect(f"postgresql://postgres:postgres@127.0.0.1:5432/{SOURCE_DB}")
    org_id = await c_source.fetchval("SELECT id FROM organizations LIMIT 1")
    broker_id = await c_source.fetchval("SELECT id FROM brokers LIMIT 1")
    await c_source.execute("""
        INSERT INTO leads (id, organization_id, broker_id, name, phone, email, status, pipeline_stage, created_at, updated_at)
        VALUES ('11111111-2222-3333-4444-555555555555', $1, $2, 'Post-Backup Critical Customer', '+919876543210', 'post_backup@example.com', 'pending', 'new', now(), now());
    """, org_id, broker_id)
    post_count = await c_source.fetchval("SELECT count(*) FROM leads")
    print(f"[POST-BACKUP WRITE] Inserted lead into source database. Total leads now: {post_count}")
    await c_source.close()

    # Step 3: Restore to RESTORED_DB to verify snapshot integrity
    cmd_restore = [
        "docker", "exec", "leadscore_postgres",
        "pg_restore", "--clean", "--if-exists", "-v", "--no-owner", "--no-privileges",
        "-d", f"postgresql://postgres:postgres@127.0.0.1:5432/{RESTORED_DB}",
        DUMP_PATH
    ]
    res_restore = subprocess.run(cmd_restore, capture_output=True, text=True)
    # pg_restore may return 0 or non-zero warnings on non-existent object drops with --clean
    print(f"[RESTORE] pg_restore executed with exit code {res_restore.returncode}.")

    # Step 4: Verify restored database contents
    c_restored = await asyncpg.connect(f"postgresql://postgres:postgres@127.0.0.1:5432/{RESTORED_DB}")
    restored_leads_count = await c_restored.fetchval("SELECT count(*) FROM leads")
    restored_post_lead = await c_restored.fetchrow("SELECT id, name FROM leads WHERE id = '11111111-2222-3333-4444-555555555555'")
    print(f"[RESTORE VERIFICATION] Restored leads count: {restored_leads_count}")
    print(f"[RESTORE VERIFICATION] Post-backup lead present in restored snapshot? {restored_post_lead is not None}")
    
    # Prove that post-backup writes are NOT in the restored DB!
    assert restored_post_lead is None, "Post-backup lead should not exist in pre-backup snapshot!"
    assert restored_leads_count == 4, f"Expected original 4 leads, found {restored_leads_count}"
    print("[PROOF ESTABLISHED] A snapshot restore inherently discards all post-backup writes!")
    await c_restored.close()

    # Cleanup
    subprocess.run(["docker", "exec", "leadscore_postgres", "rm", "-f", DUMP_PATH])
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {SOURCE_DB};")
    await admin.execute(f"DROP DATABASE IF EXISTS {RESTORED_DB};")
    await admin.close()
    print("[TEARDOWN] Dropped rehearsal databases and dump file.")

if __name__ == "__main__":
    asyncio.run(run_rehearsal())
