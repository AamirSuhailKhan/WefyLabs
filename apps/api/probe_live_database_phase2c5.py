import asyncio
import json
from decimal import Decimal
from datetime import datetime
from sqlalchemy import text
from app.database import AsyncSessionLocal, engine

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

async def probe():
    results = {}
    
    # 1. Row counts
    counts = {}
    tables = [
        ("organizations", "organizations"),
        ("organization_members", "organization_members"),
        ("brokers", "brokers"),
        ("leads", "leads"),
        ("property_listings", "property_listings"),
        ("deals", "deals"),
        ("site_visits", "site_visits"),
        ("deal_bookings", "deal_bookings"),
        ("deal_commissions", "deal_commissions"),
        ("pilot_tenants", "pilot_tenants"),
        ("pilot_observations", "pilot_observations"),
        ("pilot_human_decisions", "pilot_human_decisions"),
        ("pilot_audit_events", "pilot_audit_events"),
        ("pilot_metric_snapshots", "pilot_metric_snapshots"),
        ("pilot_stage_transitions", "pilot_stage_transitions"),
        ("pilot_action_records", "pilot_action_records"),
        ("pilot_evidence_records", "pilot_evidence_records"),
    ]
    for label, tbl in tables:
        try:
            async with AsyncSessionLocal() as session:
                res = await session.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                counts[label] = res.scalar()
        except Exception as e:
            counts[label] = f"ERROR: {str(e)}"
    results["counts"] = counts

    # 2. Pilot details
    try:
        async with AsyncSessionLocal() as session:
            pilots = (await session.execute(text("SELECT id, organization_id, pilot_stage, target_name, is_active FROM pilot_tenants"))).fetchall()
            results["pilot_tenants"] = [dict(r._mapping) for r in pilots]
    except Exception as e:
        results["pilot_tenants"] = str(e)

    # 3. Decisions & observations
    try:
        async with AsyncSessionLocal() as session:
            obs = (await session.execute(text("SELECT id, pilot_id, organization_id, lead_id, pilot_stage, execution_mode, recommended_action, is_synthetic FROM pilot_observations"))).fetchall()
            results["observations"] = [dict(r._mapping) for r in obs]
    except Exception as e:
        results["observations"] = str(e)

    try:
        async with AsyncSessionLocal() as session:
            decs = (await session.execute(text("SELECT id, observation_id, organization_id, decision_type, action_taken, is_synthetic FROM pilot_human_decisions"))).fetchall()
            results["decisions"] = [dict(r._mapping) for r in decs]
    except Exception as e:
        results["decisions"] = str(e)

    # 4. Snapshots
    try:
        async with AsyncSessionLocal() as session:
            snaps = (await session.execute(text("SELECT id, pilot_id, snapshot_date, cumulative_genuine_decisions, status, snapshot_hash FROM pilot_metric_snapshots ORDER BY snapshot_date"))).fetchall()
            results["snapshots"] = [dict(r._mapping) for r in snaps]
    except Exception as e:
        results["snapshots"] = str(e)

    # 5. Audit Events
    try:
        async with AsyncSessionLocal() as session:
            audits = (await session.execute(text("SELECT id, pilot_id, sequence_number, event_type, current_hash, previous_hash FROM pilot_audit_events ORDER BY sequence_number"))).fetchall()
            results["audit_events"] = [dict(r._mapping) for r in audits]
    except Exception as e:
        results["audit_events"] = str(e)

    # 6. pg_stat_activity (Connection deep-dive)
    try:
        async with AsyncSessionLocal() as session:
            pg_stat = (await session.execute(text("""
                SELECT pid, usename, application_name, client_addr, backend_start, state, 
                       wait_event_type, wait_event, query
                FROM pg_stat_activity 
                WHERE datname = current_database()
            """))).fetchall()
            results["pg_stat_activity"] = [
                {
                    "pid": r.pid,
                    "usename": r.usename,
                    "application_name": r.application_name,
                    "client_addr": str(r.client_addr),
                    "backend_start": r.backend_start.isoformat() if r.backend_start else None,
                    "state": r.state,
                    "wait_event_type": r.wait_event_type,
                    "wait_event": r.wait_event,
                    "query": r.query[:120] if r.query else None
                }
                for r in pg_stat
            ]
    except Exception as e:
        results["pg_stat_activity"] = str(e)

    # 7. Deals / Revenue
    try:
        async with AsyncSessionLocal() as session:
            deals = (await session.execute(text("SELECT id, organization_id, current_stage, agreed_price, currency FROM deals LIMIT 5"))).fetchall()
            results["deals"] = [dict(r._mapping) for r in deals]
    except Exception as e:
        results["deals"] = str(e)

    try:
        async with AsyncSessionLocal() as session:
            commissions = (await session.execute(text("SELECT id, deal_id, organization_id, broker_id, transaction_price, gross_commission, status FROM deal_commissions LIMIT 5"))).fetchall()
            results["commissions"] = [dict(r._mapping) for r in commissions]
    except Exception as e:
        results["commissions"] = str(e)

    await engine.dispose()
    print(json.dumps(results, indent=2, cls=CustomEncoder))

if __name__ == "__main__":
    asyncio.run(probe())
