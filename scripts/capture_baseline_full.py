"""Phase 2C.6D - Complete baseline with correct table names"""
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


async def query(sql, mode="scalar"):
    async with async_session_maker() as db:
        try:
            r = await db.execute(text(sql))
            if mode == "scalar":
                return r.scalar()
            elif mode == "rows":
                rows = r.fetchall()
                return [dict(row._mapping) for row in rows]
            elif mode == "list":
                return [row[0] for row in r.fetchall()]
        except Exception as e:
            return {"error": str(e)[:300]}


async def main():
    data = {"capture_timestamp": datetime.now(timezone.utc).isoformat()}

    # Governance - pilot_tenants
    data["pilot_tenants"] = await query("""
        SELECT id, organization_id, stage, autonomy_level,
               enrollment_date, created_at
        FROM pilot_tenants ORDER BY created_at DESC LIMIT 5
    """, "rows")

    # pilot_human_decisions
    data["pilot_human_decisions"] = await query(
        "SELECT COUNT(*) FROM pilot_human_decisions", "scalar"
    )

    # pilot_observations
    data["pilot_observations_count"] = await query(
        "SELECT COUNT(*) FROM pilot_observations", "scalar"
    )

    # pilot_evidence_records
    data["pilot_evidence_records_count"] = await query(
        "SELECT COUNT(*) FROM pilot_evidence_records", "scalar"
    )

    # pilot_audit_events
    data["pilot_audit_events_count"] = await query(
        "SELECT COUNT(*) FROM pilot_audit_events", "scalar"
    )

    # pilot_metric_snapshots
    data["pilot_metric_snapshots_count"] = await query(
        "SELECT COUNT(*) FROM pilot_metric_snapshots", "scalar"
    )

    # deal_transactions - check actual columns
    data["deal_transactions_columns"] = await query("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name='deal_transactions'
        ORDER BY ordinal_position
    """, "list")

    # deal_transactions count
    data["deal_transactions_count"] = await query(
        "SELECT COUNT(*) FROM deal_transactions", "scalar"
    )

    # Get deal amounts
    deal_cols = data["deal_transactions_columns"]
    if isinstance(deal_cols, list):
        # Find value column
        for col in ["amount", "deal_value", "value", "commission_amount", "total_amount"]:
            if col in deal_cols:
                r = await query(f"SELECT COUNT(*), COALESCE(SUM({col}),0) FROM deal_transactions", "scalar")
                data[f"deal_total_{col}"] = r
                break

    # audit_logs record count
    data["audit_logs_count"] = await query("SELECT COUNT(*) FROM audit_logs", "scalar")

    # Latest audit
    data["latest_audit_event"] = await query("""
        SELECT id, event_type, created_at FROM audit_logs
        ORDER BY created_at DESC LIMIT 3
    """, "rows")

    # Organizations
    data["organizations"] = await query("""
        SELECT id, name, created_at FROM organizations
        ORDER BY created_at LIMIT 10
    """, "rows")

    # Stage transitions
    data["pilot_stage_transitions"] = await query("""
        SELECT * FROM pilot_stage_transitions ORDER BY created_at DESC LIMIT 5
    """, "rows")

    # pilot_approval_items
    data["pilot_approval_items_count"] = await query(
        "SELECT COUNT(*) FROM pilot_approval_items", "scalar"
    )

    return data


if __name__ == "__main__":
    data = asyncio.run(main())

    def ser(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return str(obj)

    with open("scripts/phase2c6d_baseline_full.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=ser)

    print(json.dumps(data, indent=2, default=ser))
    print("\nSaved to scripts/phase2c6d_baseline_full.json")
