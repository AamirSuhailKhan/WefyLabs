"""
Phase 2C.4 — Execution Phase 0: Repository Reconstruction & Fresh Baseline
"""
import sqlite3
import json
import os
import subprocess
from datetime import datetime

DB_PATH = "test_dev.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

results = {}

# 1. Table inventory
tables = [r['name'] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
results['total_tables'] = len(tables)

key_tables = [
    'organizations', 'organization_members', 'brokers',
    'leads', 'properties', 'sales_loop_events',
    'pilot_tenants', 'pilot_observations', 'pilot_human_decisions',
    'pilot_audit_events', 'pilot_metric_snapshots',
    'deals', 'site_visits', 'opportunities', 'bookings',
    'follow_ups', 'lead_automation_states',
    'audit_logs', 'incidents',
]

table_counts = {}
for t in tables:
    try:
        cnt = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        table_counts[t] = cnt
    except Exception as e:
        table_counts[t] = f"ERROR: {e}"
results['table_counts'] = table_counts

# 2. Key entity counts
for k in key_tables:
    v = table_counts.get(k, 'MISSING')
    print(f"  {k:<40}: {v}")

# 3. Pilot state
print("\n=== PILOT TENANTS ===")
try:
    pts = cur.execute("SELECT * FROM pilot_tenants").fetchall()
    for pt in pts:
        print(dict(pt))
except Exception as e:
    print(f"ERROR: {e}")

# 4. Pilot observations
print("\n=== PILOT OBSERVATIONS ===")
try:
    obs = cur.execute("SELECT id, pilot_id, organization_id, lead_id, agent_name, is_synthetic, comparison_category, created_at FROM pilot_observations").fetchall()
    for o in obs:
        print(dict(o))
except Exception as e:
    print(f"ERROR: {e}")

# 5. Pilot human decisions
print("\n=== PILOT HUMAN DECISIONS ===")
try:
    decs = cur.execute("SELECT id, observation_id, organization_id, human_action, decision_type, reason, decided_at FROM pilot_human_decisions").fetchall()
    for d in decs:
        print(dict(d))
except Exception as e:
    print(f"ERROR: {e}")

# 6. Sales loop events
print("\n=== SALES LOOP EVENTS ===")
try:
    evts = cur.execute("SELECT id, idempotency_key, event_type, tenant_id, lead_id, processing_state, occurred_at FROM sales_loop_events").fetchall()
    for e in evts:
        print(dict(e))
except Exception as e:
    print(f"ERROR: {e}")

# 7. Pilot metric snapshots
print("\n=== PILOT METRIC SNAPSHOTS ===")
try:
    snaps = cur.execute("SELECT id, pilot_id, snapshot_date, total_events, total_observations, human_decisions, synthetic_observations, external_side_effects, created_at FROM pilot_metric_snapshots").fetchall()
    for s in snaps:
        print(dict(s))
except Exception as e:
    # try alternative column layout
    try:
        snaps2 = cur.execute("SELECT * FROM pilot_metric_snapshots LIMIT 3").fetchall()
        for s in snaps2:
            print(dict(s))
    except Exception as e2:
        print(f"ERROR: {e2}")

conn.close()

# 8. Git state
print("\n=== GIT STATE ===")
try:
    commit = subprocess.check_output(['git', 'log', '-1', '--format=%H %ai %s'], cwd='.').decode().strip()
    print(f"Last commit: {commit}")
    status = subprocess.check_output(['git', 'status', '--short'], cwd='.').decode().strip()
    modified = [l for l in status.split('\n') if l.strip() and not l.startswith('??')]
    untracked = [l for l in status.split('\n') if l.startswith('??')]
    print(f"Modified files: {len(modified)}")
    print(f"Untracked files: {len(untracked)}")
except Exception as e:
    print(f"ERROR: {e}")

# 9. Alembic migration state
print("\n=== ALEMBIC MIGRATION STATE ===")
try:
    rev = subprocess.check_output(['python', '-m', 'alembic', 'current'], cwd='.', stderr=subprocess.STDOUT).decode().strip()
    print(rev)
except Exception as e:
    print(f"ERROR: {e}")
