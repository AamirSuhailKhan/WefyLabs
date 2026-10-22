"""Phase 2C.6D - Baseline Capture (fixed - separate transactions per query)"""
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone

api_dir = Path("apps/api").resolve()
sys.path.insert(0, str(api_dir))

from dotenv import load_dotenv
load_dotenv("apps/api/.env")

from sqlalchemy import text
from app.database import async_session_maker


async def safe_query(db, sql, default=None):
    try:
        await db.rollback()
        r = await db.execute(text(sql))
        return r
    except Exception as e:
        try:
            await db.rollback()
        except:
            pass
        return None


async def capture_baseline():
    results = {
        "capture_timestamp": datetime.now(timezone.utc).isoformat(),
        "db_version": None,
        "alembic_current": [],
        "tables_found": [],
        "pilot_states": [],
        "organization_count": None,
        "broker_count": None,
        "lead_count": None,
        "human_decision_count": None,
        "observation_count": None,
        "booking_count": None,
        "total_deal_value": None,
        "daily_snapshot_count": None,
        "audit_count": None,
    }

    queries = [
        ("db_version", "SELECT version()", "scalar"),
        ("alembic_current", "SELECT version_num FROM alembic_version", "list"),
        ("tables_found", """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """, "list"),
        ("organization_count", "SELECT COUNT(*) FROM organizations", "scalar"),
        ("broker_count", "SELECT COUNT(*) FROM brokers", "scalar"),
        ("lead_count", "SELECT COUNT(*) FROM leads", "scalar"),
        ("human_decision_count", "SELECT COUNT(*) FROM human_decisions", "scalar"),
        ("observation_count", "SELECT COUNT(*) FROM pilot_observations", "scalar"),
        ("daily_snapshot_count", "SELECT COUNT(*) FROM pilot_daily_snapshots", "scalar"),
        ("audit_count", "SELECT COUNT(*) FROM audit_logs", "scalar"),
    ]

    for key, sql, mode in queries:
        async with async_session_maker() as db:
            try:
                r = await db.execute(text(sql))
                if mode == "scalar":
                    results[key] = r.scalar()
                elif mode == "list":
                    rows = r.fetchall()
                    results[key] = [row[0] for row in rows]
                elif mode == "rows":
                    rows = r.fetchall()
                    results[key] = [dict(row._mapping) for row in rows]
            except Exception as e:
                results[f"{key}_error"] = str(e)[:200]

    # Deal transactions with separate session
    async with async_session_maker() as db:
        try:
            r = await db.execute(text("SELECT COUNT(*), COALESCE(SUM(deal_value),0) FROM deal_transactions"))
            row = r.fetchone()
            results["booking_count"] = row[0]
            results["total_deal_value"] = float(row[1])
        except Exception as e:
            results["booking_error"] = str(e)[:200]

    # Pilot state via governance tables
    async with async_session_maker() as db:
        try:
            r = await db.execute(text("""
                SELECT id, tenant_id, stage, autonomy_level, enrollment_date,
                       genuine_days_elapsed, verified_human_decisions,
                       stage2_eligible, created_at
                FROM pilot_states ORDER BY created_at DESC LIMIT 5
            """))
            rows = r.fetchall()
            results["pilot_states"] = [dict(row._mapping) for row in rows]
        except Exception as e:
            results["pilot_states_error"] = str(e)[:200]

    # Find correct governance table name
    async with async_session_maker() as db:
        try:
            r = await db.execute(text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_name LIKE '%pilot%'
                OR table_schema='public' AND table_name LIKE '%governance%'
                OR table_schema='public' AND table_name LIKE '%stage%'
                ORDER BY table_name
            """))
            rows = r.fetchall()
            results["governance_tables"] = [row[0] for row in rows]
        except Exception as e:
            results["governance_tables_error"] = str(e)[:200]

    # Provider dispatches
    async with async_session_maker() as db:
        try:
            r = await db.execute(text("SELECT COUNT(*) FROM provider_dispatch_log WHERE status != 'shadow'"))
            results["real_provider_dispatches"] = r.scalar()
        except Exception as e:
            results["real_provider_dispatches_note"] = str(e)[:200]

    return results


if __name__ == "__main__":
    data = asyncio.run(capture_baseline())

    def make_serializable(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return str(obj)

    output = json.dumps(data, indent=2, default=make_serializable)
    print(output)

    with open("scripts/phase2c6d_baseline.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=make_serializable)

    print("\nDone - saved to scripts/phase2c6d_baseline.json")
