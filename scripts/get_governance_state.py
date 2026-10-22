"""Get precise governance state from pilot_tenants"""
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone, date

api_dir = Path("apps/api").resolve()
sys.path.insert(0, str(api_dir))

from dotenv import load_dotenv
load_dotenv("apps/api/.env")

from sqlalchemy import text
from app.database import async_session_maker


async def main():
    async with async_session_maker() as db:
        # Get actual columns of pilot_tenants
        r = await db.execute(text("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema='public' AND table_name='pilot_tenants'
            ORDER BY ordinal_position
        """))
        cols = [(row[0], row[1]) for row in r.fetchall()]
        print("pilot_tenants columns:", cols)

    async with async_session_maker() as db:
        # Get all pilot_tenants rows
        r = await db.execute(text("SELECT * FROM pilot_tenants ORDER BY created_at DESC LIMIT 5"))
        rows = r.fetchall()
        keys = r.keys()
        tenants = [dict(zip(keys, row)) for row in rows]
        print("\npilot_tenants rows:")
        for t in tenants:
            print(json.dumps(t, indent=2, default=str))

    async with async_session_maker() as db:
        # Get all pilot_human_decisions
        r = await db.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='pilot_human_decisions'
            ORDER BY ordinal_position
        """))
        phd_cols = [row[0] for row in r.fetchall()]
        print("\npilot_human_decisions columns:", phd_cols)

    async with async_session_maker() as db:
        r = await db.execute(text("SELECT * FROM pilot_human_decisions ORDER BY created_at DESC LIMIT 10"))
        rows = r.fetchall()
        keys = r.keys()
        decisions = [dict(zip(keys, row)) for row in rows]
        print("\npilot_human_decisions rows:")
        for d in decisions:
            print(json.dumps(d, indent=2, default=str))

    async with async_session_maker() as db:
        r = await db.execute(text("SELECT * FROM pilot_observations ORDER BY created_at DESC LIMIT 10"))
        rows = r.fetchall()
        keys = r.keys()
        obs = [dict(zip(keys, row)) for row in rows]
        print("\npilot_observations rows:")
        for o in obs:
            print(json.dumps(o, indent=2, default=str))

    async with async_session_maker() as db:
        # Calculate genuine days from enrollment
        r = await db.execute(text("""
            SELECT
                enrollment_date,
                NOW() AS now,
                EXTRACT(DAY FROM NOW() - enrollment_date::timestamp) AS days_elapsed
            FROM pilot_tenants
            ORDER BY created_at DESC LIMIT 1
        """))
        row = r.fetchone()
        if row:
            print(f"\nEnrollment date: {row[0]}")
            print(f"Now: {row[1]}")
            print(f"Days elapsed: {row[2]}")

    async with async_session_maker() as db:
        r = await db.execute(text("SELECT * FROM pilot_audit_events ORDER BY created_at DESC LIMIT 10"))
        rows = r.fetchall()
        keys = r.keys()
        events = [dict(zip(keys, row)) for row in rows]
        print("\npilot_audit_events rows:")
        for e in events:
            print(json.dumps(e, indent=2, default=str))

    async with async_session_maker() as db:
        r = await db.execute(text("SELECT * FROM pilot_metric_snapshots ORDER BY created_at DESC LIMIT 5"))
        rows = r.fetchall()
        keys = r.keys()
        snaps = [dict(zip(keys, row)) for row in rows]
        print("\npilot_metric_snapshots rows:")
        for s in snaps:
            print(json.dumps(s, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
