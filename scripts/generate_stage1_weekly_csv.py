#!/usr/bin/env python3
"""
scripts/generate_stage1_weekly_csv.py
=====================================
PHASE 2C.6A — Deterministic Weekly CSV Generator

Generates the weekly Stage-1 pilot evidence CSV directly from live PostgreSQL.
No manual editing. Database -> Aggregation -> CSV.
"""
import asyncio
import csv
import os
import sys
from datetime import date, timedelta


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


async def generate_weekly_csv():
    import asyncpg
    pg_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_url, timeout=30)

    pilot = await conn.fetchrow("SELECT id, organization_id, stage_entered_at FROM pilot_tenants LIMIT 1")
    if not pilot:
        print("No pilot enrolled.")
        return

    org_id = str(pilot["organization_id"])
    start_date = pilot["stage_entered_at"].date()
    end_date = date(2026, 10, 5)

    rows = []
    current = start_date
    day_num = 1

    while current <= end_date:
        leads = await conn.fetchval(
            "SELECT COUNT(*) FROM leads WHERE organization_id = $1 AND created_at::date <= $2::date",
            org_id, current
        ) or 0

        obs = await conn.fetchval(
            "SELECT COUNT(*) FROM pilot_observations WHERE organization_id = $1 AND is_synthetic = false AND observed_at::date <= $2::date",
            org_id, current
        ) or 0

        decisions = await conn.fetchval(
            "SELECT COUNT(*) FROM pilot_human_decisions WHERE organization_id = $1 AND decided_at::date <= $2::date",
            org_id, current
        ) or 0

        dispatches = await conn.fetchval(
            "SELECT COUNT(*) FROM pilot_action_records WHERE organization_id = $1 AND execution_mode != 'SHADOW' AND created_at::date <= $2::date",
            org_id, current
        ) or 0

        visits = await conn.fetchval(
            "SELECT COUNT(*) FROM site_visits WHERE organization_id = $1 AND created_at::date <= $2::date",
            org_id, current
        ) or 0

        deals = await conn.fetchval(
            "SELECT COUNT(*) FROM deals WHERE organization_id = $1 AND created_at::date <= $2::date",
            org_id, current
        ) or 0

        bookings = await conn.fetchval(
            "SELECT COUNT(*) FROM deal_bookings WHERE created_at::date <= $1::date",
            current
        ) or 0

        commissions = await conn.fetchval(
            "SELECT COALESCE(SUM(gross_commission), 0) FROM deal_commissions WHERE created_at::date <= $1::date",
            current
        ) or 0

        rows.append({
            "day": f"Day {day_num}",
            "date": str(current),
            "organization_id": org_id,
            "organization_name": "Aamir Suhail's Agency",
            "pilot_stage": "STAGE_1_SHADOW",
            "autonomy_level": 0,
            "cumulative_leads": leads,
            "cumulative_observations": obs,
            "cumulative_decisions": decisions,
            "cumulative_dispatches": dispatches,
            "site_visits": visits,
            "opportunities": deals,
            "bookings": bookings,
            "commission_inr": float(commissions),
            "stage_2_eligible": False,
        })
        current += timedelta(days=1)
        day_num += 1

    await conn.close()

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=r"C:\Users\aamir\.gemini\antigravity-ide\brain\db97d69f-81f9-4ab9-9ace-199d4e308384\PHASE2C_6B_WEEKLY_PILOT_EVIDENCE.csv")
    args = parser.parse_args()

    output_csv = args.output
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated weekly evidence CSV: {output_csv} ({len(rows)} rows)")


if __name__ == "__main__":
    asyncio.run(generate_weekly_csv())
