#!/usr/bin/env python3
"""
scripts/collect_phase2c6b_baseline.py
======================================
Collects the complete authoritative production baseline for Phase 2C.6B.
Queries live Supabase PostgreSQL directly.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal


def load_env():
    env_path = r"C:\Users\aamir\OneDrive\Desktop\crm real state\apps\api\.env"
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


load_env()
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def json_serial(obj):
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)


async def collect_baseline():
    import asyncpg
    pg_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_url, timeout=30)

    data = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "database_host": "aws-0-ap-south-1.pooler.supabase.com:5432",
    }

    # Alembic
    rev = await conn.fetchval("SELECT version_num FROM alembic_version")
    data["alembic_version"] = rev

    # Table counts
    tables = [
        "organizations", "users", "brokers", "pilot_tenants",
        "pilot_stage_transitions", "pilot_observations", "pilot_human_decisions",
        "pilot_audit_events", "pilot_action_records", "pilot_metric_snapshots",
        "pilot_evidence_records", "pilot_approval_items",
        "leads", "properties", "site_visits", "deals", "deal_bookings", "deal_commissions"
    ]
    counts = {}
    for t in tables:
        try:
            cnt = await conn.fetchval(f"SELECT COUNT(*) FROM {t}")
            counts[t] = cnt
        except Exception as e:
            counts[t] = f"ERROR: {e}"
    data["table_counts"] = counts

    # Organizations
    orgs = await conn.fetch("SELECT id, name, created_at FROM organizations ORDER BY created_at")
    data["organizations"] = [dict(o) for o in orgs]

    # Pilot Tenants
    pilots = await conn.fetch("SELECT * FROM pilot_tenants")
    data["pilot_tenants"] = [dict(p) for p in pilots]

    # Pilot Observations
    obs = await conn.fetch("SELECT * FROM pilot_observations ORDER BY observed_at")
    data["pilot_observations"] = [dict(o) for o in obs]

    # Human Decisions
    dec = await conn.fetch("SELECT * FROM pilot_human_decisions ORDER BY decided_at")
    data["pilot_human_decisions"] = [dict(d) for d in dec]

    # Audit Events
    aud = await conn.fetch("SELECT * FROM pilot_audit_events ORDER BY sequence_number")
    data["pilot_audit_events"] = [dict(a) for a in aud]

    # Action Records
    act = await conn.fetch("SELECT * FROM pilot_action_records")
    data["pilot_action_records"] = [dict(a) for a in act]

    # Leads
    leads = await conn.fetch("SELECT * FROM leads ORDER BY created_at")
    data["leads"] = [dict(l) for l in leads]

    # Bookings & Commissions
    bookings = await conn.fetch("SELECT * FROM deal_bookings")
    data["deal_bookings"] = [dict(b) for b in bookings]

    commissions = await conn.fetch("SELECT * FROM deal_commissions")
    data["deal_commissions"] = [dict(c) for c in commissions]

    # Per-organization breakdown
    org_breakdown = {}
    for o in orgs:
        oid = str(o["id"])
        oname = o["name"]
        is_pilot = any(str(p["organization_id"]) == oid for p in pilots)
        pilot_row = next((p for p in pilots if str(p["organization_id"]) == oid), None)
        o_leads = [l for l in leads if str(l["organization_id"]) == oid]
        o_obs = [ob for ob in obs if str(ob["organization_id"]) == oid]
        o_dec = [d for d in dec if str(d["organization_id"]) == oid]
        o_bookings = []
        if bookings and "organization_id" in bookings[0]:
            o_bookings = [b for b in bookings if str(b["organization_id"]) == oid]

        org_breakdown[oid] = {
            "name": oname,
            "is_pilot": is_pilot,
            "pilot_stage": pilot_row["current_stage"] if pilot_row else "NOT_ENROLLED",
            "autonomy_level": pilot_row["configured_autonomy_level"] if pilot_row else None,
            "lead_count": len(o_leads),
            "observation_count": len(o_obs),
            "decision_count": len(o_dec),
            "booking_count": len(o_bookings),
        }
    data["organization_breakdown"] = org_breakdown

    await conn.close()

    out_file = r"C:\Users\aamir\.gemini\antigravity-ide\brain\db97d69f-81f9-4ab9-9ace-199d4e308384\scratch\phase2c6b_live_baseline.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, default=json_serial, indent=2)

    print(f"Collected live baseline: {out_file}")
    print(f"Alembic: {rev}")
    print(f"Organizations: {len(orgs)}")
    print(f"Pilot tenants: {len(pilots)}")
    print(f"Observations: {len(obs)}")
    print(f"Decisions: {len(dec)}")
    print(f"Audit events: {len(aud)}")
    print(f"Action records: {len(act)}")


if __name__ == "__main__":
    asyncio.run(collect_baseline())
