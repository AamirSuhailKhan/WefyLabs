import asyncio
import json
import uuid
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy import text
from app.database import AsyncSessionLocal, engine

class RobustEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (Decimal, uuid.UUID)):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if hasattr(obj, "_mapping"):
            return dict(obj._mapping)
        return super().default(obj)

async def collect():
    data = {}
    tables = [
        "organizations",
        "organization_members",
        "brokers",
        "pilot_tenants",
        "leads",
        "property_listings",
        "deals",
        "site_visits",
        "deal_bookings",
        "deal_commissions",
        "pilot_observations",
        "pilot_human_decisions",
        "pilot_metric_snapshots",
        "pilot_audit_events",
        "pilot_stage_transitions",
        "pilot_action_records",
        "pilot_evidence_records"
    ]

    async with AsyncSessionLocal() as session:
        for t in tables:
            try:
                res = await session.execute(text(f"SELECT * FROM {t}"))
                rows = res.fetchall()
                data[t] = [dict(r._mapping) for r in rows]
                print(f"[OK] Table {t}: {len(rows)} rows")
            except Exception as e:
                data[t] = f"ERROR: {str(e)}"
                print(f"[FAIL] Table {t}: {str(e)}")

        # Connection forensics from pg_stat_activity
        try:
            conns = await session.execute(text("""
                SELECT pid, usename, application_name, client_addr, backend_start, state,
                       state_change, wait_event_type, wait_event, query
                FROM pg_stat_activity
                WHERE datname = current_database()
                ORDER BY backend_start
            """))
            data["pg_stat_activity"] = [
                {
                    "pid": r.pid,
                    "usename": r.usename,
                    "application_name": r.application_name,
                    "client_addr": str(r.client_addr),
                    "backend_start": r.backend_start.isoformat() if r.backend_start else None,
                    "state_change": r.state_change.isoformat() if r.state_change else None,
                    "state": r.state,
                    "wait_event_type": r.wait_event_type,
                    "wait_event": r.wait_event,
                    "query": r.query[:160] if r.query else None
                }
                for r in conns.fetchall()
            ]
            print(f"[OK] pg_stat_activity: {len(data['pg_stat_activity'])} connections")
        except Exception as e:
            data["pg_stat_activity"] = f"ERROR: {str(e)}"

        # Settings
        try:
            db_settings = await session.execute(text("""
                SELECT name, setting, unit, context 
                FROM pg_settings 
                WHERE name IN ('max_connections', 'superuser_reserved_connections', 'pool_mode', 'default_transaction_isolation')
            """))
            data["pg_settings"] = [dict(r._mapping) for r in db_settings.fetchall()]
        except Exception as e:
            data["pg_settings"] = f"ERROR: {str(e)}"

    await engine.dispose()
    
    with open("phase2c6_live_baseline_raw.json", "w") as f:
        json.dump(data, f, indent=2, cls=RobustEncoder)
    
    print("Baseline collection complete and written to phase2c6_live_baseline_raw.json")

if __name__ == "__main__":
    asyncio.run(collect())
