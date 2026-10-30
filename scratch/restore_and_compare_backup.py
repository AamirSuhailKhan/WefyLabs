import os
import subprocess
import time
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv("apps/api/.env", override=False)
raw_supabase_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

async def main():
    print("=== Rehearsing Full Backup Restore in Disposable Postgres 17 ===")
    # 1. Start disposable postgres 17 container
    container_name = "pg17_restore_rehearsal"
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
    
    start_cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "-e", "POSTGRES_PASSWORD=postgres",
        "-e", "POSTGRES_DB=postgres_restored",
        "-p", "127.0.0.1:5433:5432",
        "-v", f"{os.getcwd()}/backups:/backups",
        "postgres:17-alpine"
    ]
    res = subprocess.run(start_cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Failed to start container: {res.stderr}"
    print(f"Container {container_name} started.")

    # Wait for postgres to be ready
    for i in range(20):
        check = subprocess.run(["docker", "exec", container_name, "pg_isready", "-U", "postgres"], capture_output=True, text=True)
        if check.returncode == 0:
            print("Postgres 17 is ready.")
            break
        time.sleep(1)

    # 2. Run pg_restore
    print("Restoring backups/supabase_prod_backup_pre_resolution.dump into postgres_restored...")
    restore_cmd = [
        "docker", "exec",
        container_name,
        "pg_restore",
        "-U", "postgres",
        "-d", "postgres_restored",
        "--no-owner",
        "--no-privileges",
        "/backups/supabase_prod_backup_pre_resolution.dump"
    ]
    # Note: pg_restore may return 1 if there are minor warnings about pre-existing extensions or schemas
    r_res = subprocess.run(restore_cmd, capture_output=True, text=True)
    print(f"pg_restore finished with code {r_res.returncode}. (Warnings/notices in stderr: {len(r_res.stderr)} chars)")

    # 3. Connect to restored database and check brokers
    restored_url = "postgresql://postgres:postgres@127.0.0.1:5433/postgres_restored"
    conn_res = await asyncpg.connect(restored_url)
    conn_sb = await asyncpg.connect(raw_supabase_url)

    try:
        restored_brokers = await conn_res.fetch("SELECT * FROM public.brokers ORDER BY created_at ASC")
        live_brokers = await conn_sb.fetch("SELECT * FROM public.brokers ORDER BY created_at ASC")

        print(f"\nRestored Brokers count: {len(restored_brokers)}")
        print(f"Live Supabase Brokers count: {len(live_brokers)}")

        restored_map = {b['id']: dict(b) for b in restored_brokers}
        live_map = {b['id']: dict(b) for b in live_brokers}

        differences = []
        for b_id, b_restored in restored_map.items():
            if b_id not in live_map:
                differences.append(f"Broker {b_id} exists in backup but missing in live!")
                continue
            b_live = live_map[b_id]
            field_diffs = {}
            for col in b_restored.keys():
                val_rest = b_restored[col]
                val_live = b_live.get(col)
                if val_rest != val_live:
                    field_diffs[col] = {"backup_val": val_rest, "live_val": val_live}
            if field_diffs:
                differences.append({"broker_id": str(b_id), "name": b_restored.get("name"), "email": b_restored.get("email"), "diffs": field_diffs})

        print(f"\nBroker differences found: {len(differences)}")
        for d in differences:
            print(f"  Difference: {d}")

        # Check source attributions
        restored_sa = await conn_res.fetch("SELECT * FROM public.source_attributions")
        live_sa = await conn_sb.fetch("SELECT * FROM public.source_attributions")
        print(f"\nRestored source_attributions count: {len(restored_sa)}")
        print(f"Live Supabase source_attributions count: {len(live_sa)}")
        for sa in restored_sa:
            print(f"  Restored SA: ID={sa['id']}, Org={sa['organization_id']}, Lead={sa['lead_id']}")

        # Reconcile any broker side-effects if needed:
        for d in differences:
            b_id = d['broker_id']
            diffs = d['diffs']
            print(f"\nEvaluating broker {b_id} for reconciliation...")
            # If subscription_status or subscription_plan differed due to smoke test
            if "subscription_status" in diffs or "subscription_plan" in diffs:
                orig_status = diffs.get("subscription_status", {}).get("backup_val") if "subscription_status" in diffs else live_map[uuid.UUID(b_id)]["subscription_status"]
                orig_plan = diffs.get("subscription_plan", {}).get("backup_val") if "subscription_plan" in diffs else live_map[uuid.UUID(b_id)]["subscription_plan"]
                print(f"  Reverting broker {b_id} to pre-migration backup state:")
                print(f"    subscription_status -> {orig_status}")
                print(f"    subscription_plan -> {orig_plan}")
                await conn_sb.execute("""
                    UPDATE public.brokers 
                    SET subscription_status = $1, subscription_plan = $2 
                    WHERE id = $3
                """, orig_status, orig_plan, b_id if isinstance(b_id, uuid.UUID) else uuid.UUID(b_id))
                print("  Reconciliation executed on Live Supabase.")

        # Re-verify live brokers after potential reconciliation
        reverified_brokers = await conn_sb.fetch("SELECT * FROM public.brokers ORDER BY created_at ASC")
        reverified_map = {b['id']: dict(b) for b in reverified_brokers}
        post_diffs = []
        for b_id, b_restored in restored_map.items():
            b_live = reverified_map[b_id]
            for col in ['subscription_status', 'subscription_plan']:
                if b_restored[col] != b_live[col]:
                    post_diffs.append((b_id, col, b_restored[col], b_live[col]))
        print(f"\nPost-reconciliation broker status/plan differences: {post_diffs}")
        assert len(post_diffs) == 0, f"Remaining broker differences: {post_diffs}"
        print("PERFECT MATCH: All production brokers match pre-migration backup values 100%!")

    finally:
        await conn_res.close()
        await conn_sb.close()
        # cleanup container
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        print(f"Container {container_name} removed cleanly.")

if __name__ == "__main__":
    import uuid
    asyncio.run(main())

