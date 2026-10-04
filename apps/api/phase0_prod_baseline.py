"""
Phase 2C.4 — Execution Phase 0: Production DB Baseline (Fixed)
"""
import asyncio
import asyncpg
from datetime import datetime, timezone

DB_URL = "postgresql://postgres.iymirycycichjbllucsr:BeetleLabs%402026@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"

async def get_columns(conn, table):
    """Return actual column names for a table"""
    rows = await conn.fetch("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = $1 AND table_schema = 'public'
        ORDER BY ordinal_position
    """, table)
    return [r['column_name'] for r in rows]

async def run():
    conn = await asyncpg.connect(DB_URL)
    now_ts = await conn.fetchval("SELECT CURRENT_TIMESTAMP")
    pg_ver = await conn.fetchval("SELECT version()")

    print("=" * 70)
    print("PHASE 2C.4 — EXECUTION PHASE 0: FRESH PRODUCTION BASELINE")
    print("=" * 70)
    print(f"Timestamp: {now_ts}")
    print(f"PostgreSQL: {pg_ver.split(',')[0]}")

    # ─── 1. TABLE COUNTS ───────────────────────────────────────────────────────
    tables = [
        'organizations', 'organization_members', 'brokers', 'leads',
        'sales_loop_events', 'pilot_tenants', 'pilot_observations',
        'pilot_human_decisions', 'pilot_audit_events', 'pilot_metric_snapshots',
        'lead_automation_states', 'alembic_version',
    ]
    print("\n--- TABLE COUNTS ---")
    for t in tables:
        try:
            cnt = await conn.fetchval(f'SELECT COUNT(*) FROM "{t}"')
            print(f"  {t:<40}: {cnt}")
        except Exception as e:
            print(f"  {t:<40}: MISSING")

    # ─── 2. ACTIVE CONNECTIONS ─────────────────────────────────────────────────
    print("\n--- ACTIVE CONNECTIONS ---")
    conns = await conn.fetch("""
        SELECT state, application_name, count(*)
        FROM pg_stat_activity
        GROUP BY state, application_name ORDER BY count DESC
    """)
    total = sum(r['count'] for r in conns)
    for r in conns:
        print(f"  state={r['state']}, app={r['application_name']}, count={r['count']}")
    print(f"  TOTAL: {total}")

    # ─── 3. ALEMBIC STATE ──────────────────────────────────────────────────────
    print("\n--- ALEMBIC MIGRATION STATE ---")
    rev = await conn.fetchrow("SELECT version_num FROM alembic_version")
    print(f"  Current revision: {rev['version_num'] if rev else 'UNKNOWN'}")

    # ─── 4. PILOT TENANT ───────────────────────────────────────────────────────
    print("\n--- PILOT TENANTS ---")
    cols = await get_columns(conn, 'pilot_tenants')
    print(f"  Columns: {cols}")
    pts = await conn.fetch("SELECT * FROM pilot_tenants")
    for pt in pts:
        d = dict(pt)
        elapsed = (now_ts - d.get('enrolled_at')).total_seconds() / 86400 if d.get('enrolled_at') else 0
        print(f"  id={d.get('id')}, org={d.get('organization_id')}, stage={d.get('current_stage')}, status={d.get('pilot_status')}, autonomy={d.get('configured_autonomy_level')}, elapsed_days={elapsed:.3f}")

    # ─── 5. PILOT OBSERVATIONS ─────────────────────────────────────────────────
    print("\n--- PILOT OBSERVATIONS ---")
    obs_cols = await get_columns(conn, 'pilot_observations')
    print(f"  Columns: {obs_cols}")
    obs = await conn.fetch("SELECT * FROM pilot_observations ORDER BY created_at DESC LIMIT 5")
    for o in obs:
        d = dict(o)
        print(f"  id={d.get('id')}, agent_id={d.get('agent_id')}, is_synthetic={d.get('is_synthetic')}, comparison_category={d.get('comparison_category')}, created_at={d.get('created_at')}")

    # ─── 6. PILOT HUMAN DECISIONS ──────────────────────────────────────────────
    print("\n--- PILOT HUMAN DECISIONS ---")
    dec_cols = await get_columns(conn, 'pilot_human_decisions')
    print(f"  Columns: {dec_cols}")
    decs = await conn.fetch("SELECT * FROM pilot_human_decisions ORDER BY created_at DESC LIMIT 5")
    for d in decs:
        dd = dict(d)
        print(f"  id={dd.get('id')}, action={dd.get('action_taken') or dd.get('human_action')}, decision_type={dd.get('decision_type')}, reason_snippet={str(dd.get('reason',''))[:60]}")

    # ─── 7. SALES LOOP EVENTS ─────────────────────────────────────────────────
    print("\n--- SALES LOOP EVENTS ---")
    evt_cols = await get_columns(conn, 'sales_loop_events')
    print(f"  Columns: {evt_cols}")
    evts = await conn.fetch("SELECT * FROM sales_loop_events ORDER BY created_at DESC LIMIT 5")
    for e in evts:
        d = dict(e)
        print(f"  id={d.get('id')}, type={d.get('event_type')}, state={d.get('processing_state')}, key={d.get('idempotency_key')}")

    # ─── 8. PILOT METRIC SNAPSHOTS ────────────────────────────────────────────
    print("\n--- PILOT METRIC SNAPSHOTS ---")
    snap_cols = await get_columns(conn, 'pilot_metric_snapshots')
    print(f"  Columns: {snap_cols}")
    snaps = await conn.fetch("SELECT * FROM pilot_metric_snapshots ORDER BY created_at DESC LIMIT 5")
    for s in snaps:
        d = dict(s)
        print(f"  id={d.get('id')}, metric={d.get('metric_name')}, period={d.get('period_start')} to {d.get('period_end')}, value={d.get('metric_value')}, sample={d.get('sample_size')}")

    # ─── 9. ORGANIZATIONS ─────────────────────────────────────────────────────
    print("\n--- ORGANIZATIONS (ALL) ---")
    orgs = await conn.fetch("SELECT id, name, plan, created_at FROM organizations ORDER BY created_at")
    org_count = len(orgs)
    for o in orgs:
        print(f"  {dict(o)}")
    print(f"  TOTAL ORGANIZATIONS: {org_count}")

    # ─── 10. KILL SWITCH STATE ────────────────────────────────────────────────
    print("\n--- KILL SWITCH / EMERGENCY PAUSE STATE ---")
    try:
        # try finding automation_pause_flags or emergency_pause table
        kstabs = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema='public' AND table_name ILIKE '%pause%'
        """)
        print(f"  Emergency pause tables: {[r['table_name'] for r in kstabs]}")
    except Exception as e:
        print(f"  ERROR: {e}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(run())
