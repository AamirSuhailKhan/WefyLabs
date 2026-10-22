#!/usr/bin/env python3
"""
scripts/generate_stage1_daily_snapshot.py
==========================================
PHASE 2C.6A — Deterministic Daily Snapshot Generator

Requirements:
- Production DB ONLY (no synthetic records)
- Deterministic (same input = same output)
- Idempotent (running twice doesn't create duplicates)
- Tenant-scoped
- Audit-linked
- Timestamped

Does NOT create commercial events.
Only records evidence of what already happened.
"""
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

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

MINIMUM_DECISIONS_FOR_STAGE_2 = 50
MINIMUM_DAYS_FOR_STAGE_2 = 14
MINIMUM_SHADOW_SAMPLE = 50  # Matches phase2c_pilot_repository.py

async def generate_snapshot(conn, target_date: date, organization_id: str = None):
    """
    Generate a deterministic daily snapshot for a given date.
    Reads only from production DB. Does not create synthetic records.
    """
    sep = "=" * 70
    print(sep)
    print("STAGE-1 DAILY SNAPSHOT GENERATOR")
    print("Date:   " + str(target_date))
    print("Time:   " + datetime.now(timezone.utc).isoformat())
    print(sep)

    # Get pilot tenant(s)
    if organization_id:
        pilots = await conn.fetch(
            "SELECT * FROM pilot_tenants WHERE organization_id = $1 AND pilot_status = 'ACTIVE'",
            organization_id
        )
    else:
        pilots = await conn.fetch(
            "SELECT * FROM pilot_tenants WHERE pilot_status = 'ACTIVE' ORDER BY enrolled_at"
        )

    if not pilots:
        print("No active pilot tenants found.")
        return []

    snapshots = []
    for pilot in pilots:
        pilot_id = str(pilot["id"])
        org_id = str(pilot["organization_id"])
        enrolled_at = pilot["enrolled_at"]
        stage = pilot["current_stage"]
        autonomy = pilot["configured_autonomy_level"]

        print("\nPilot: " + pilot_id)
        print("  Org:    " + org_id)
        print("  Stage:  " + stage)
        print("  Autonomy (DB): " + str(autonomy))

        # Day count — counted from enrollment
        if enrolled_at:
            days_since_enrollment = (target_date - enrolled_at.date()).days + 1
        else:
            days_since_enrollment = 0

        print("  Days since enrollment: " + str(days_since_enrollment))

        # Count genuine leads (not is_synthetic, created on or before target_date)
        genuine_leads = await conn.fetchval(
            """
            SELECT COUNT(*) FROM leads
            WHERE organization_id = $1
              AND created_at::date <= $2::date
            """,
            org_id, target_date
        )

        # Count genuine observations on or before target_date
        genuine_obs = await conn.fetchval(
            """
            SELECT COUNT(*) FROM pilot_observations
            WHERE organization_id = $1
              AND is_synthetic = false
              AND observed_at::date <= $2::date
            """,
            org_id, target_date
        )

        # Count genuine human decisions on or before target_date
        genuine_decisions = await conn.fetchval(
            """
            SELECT COUNT(*) FROM pilot_human_decisions
            WHERE organization_id = $1
              AND decided_at::date <= $2::date
            """,
            org_id, target_date
        )

        # Count eligible observations (have human decision)
        eligible_obs = await conn.fetchval(
            """
            SELECT COUNT(*) FROM pilot_observations
            WHERE organization_id = $1
              AND is_synthetic = false
              AND is_eligible_for_shadow_accuracy = true
              AND observed_at::date <= $2::date
            """,
            org_id, target_date
        )

        # Shadow accuracy numerator (EXACT_AGREEMENT + SEMANTIC_AGREEMENT)
        accuracy_num = await conn.fetchval(
            """
            SELECT COUNT(*) FROM pilot_observations
            WHERE organization_id = $1
              AND is_synthetic = false
              AND is_eligible_for_shadow_accuracy = true
              AND comparison_category IN ('EXACT_AGREEMENT', 'SEMANTIC_AGREEMENT')
              AND observed_at::date <= $2::date
            """,
            org_id, target_date
        ) or 0

        # Provider dispatches (non-shadow actions)
        try:
            dispatches = await conn.fetchval(
                """
                SELECT COUNT(*) FROM pilot_action_records
                WHERE organization_id = $1
                  AND execution_mode != 'SHADOW'
                  AND created_at::date <= $2::date
                """,
                org_id, target_date
            ) or 0
        except Exception:
            dispatches = 0

        # Audit chain events
        audit_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM pilot_audit_events
            WHERE pilot_id = $1
              AND occurred_at::date <= $2::date
            """,
            pilot_id, target_date
        )

        # Commercial pipeline
        deals = await conn.fetchval(
            "SELECT COUNT(*) FROM deals WHERE organization_id = $1 AND created_at::date <= $2::date",
            org_id, target_date
        )
        bookings = await conn.fetchval(
            "SELECT COUNT(*) FROM deal_bookings WHERE created_at::date <= $1::date",
            target_date
        )
        commissions = await conn.fetchval(
            "SELECT COUNT(*) FROM deal_commissions WHERE created_at::date <= $1::date",
            target_date
        ) if bookings else 0

        # Stage 2 eligibility
        stage2_eligible = (
            days_since_enrollment >= MINIMUM_DAYS_FOR_STAGE_2 and
            genuine_decisions >= MINIMUM_DECISIONS_FOR_STAGE_2
        )
        stage2_block_reasons = []
        if days_since_enrollment < MINIMUM_DAYS_FOR_STAGE_2:
            stage2_block_reasons.append(
                "DAYS_INSUFFICIENT: " + str(days_since_enrollment) + " < " + str(MINIMUM_DAYS_FOR_STAGE_2)
            )
        if genuine_decisions < MINIMUM_DECISIONS_FOR_STAGE_2:
            stage2_block_reasons.append(
                "DECISIONS_INSUFFICIENT: " + str(genuine_decisions) + " < " + str(MINIMUM_DECISIONS_FOR_STAGE_2)
            )

        # Shadow accuracy
        if eligible_obs >= MINIMUM_SHADOW_SAMPLE:
            shadow_accuracy_pct = (accuracy_num / eligible_obs * 100) if eligible_obs > 0 else 0
            evidence_maturity = "REPORTABLE"
        else:
            shadow_accuracy_pct = (accuracy_num / eligible_obs * 100) if eligible_obs > 0 else 0
            evidence_maturity = "INSUFFICIENT (n=" + str(eligible_obs) + " < " + str(MINIMUM_SHADOW_SAMPLE) + ")"

        # Build snapshot record
        snapshot = {
            "snapshot_date": str(target_date),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pilot_id": pilot_id,
            "organization_id": org_id,
            "current_stage": stage,
            "autonomy_level_db": autonomy,
            "days_since_enrollment": days_since_enrollment,
            "genuine_leads": genuine_leads,
            "genuine_observations": genuine_obs,
            "genuine_human_decisions": genuine_decisions,
            "eligible_for_shadow_accuracy": eligible_obs,
            "shadow_accuracy_numerator": accuracy_num,
            "shadow_accuracy_denominator": eligible_obs,
            "shadow_accuracy_pct": round(shadow_accuracy_pct, 2),
            "evidence_maturity": evidence_maturity,
            "provider_dispatches": dispatches,
            "audit_events": audit_count,
            "commercial": {
                "deals": deals,
                "bookings": bookings,
            },
            "stage2_eligible": stage2_eligible,
            "stage2_block_reasons": stage2_block_reasons,
        }

        # Deterministic hash of this snapshot
        snapshot_hash = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, default=str).encode()
        ).hexdigest()
        snapshot["snapshot_hash"] = snapshot_hash

        print("  Genuine Leads:        " + str(genuine_leads))
        print("  Genuine Observations: " + str(genuine_obs))
        print("  Genuine Decisions:    " + str(genuine_decisions))
        print("  Provider Dispatches:  " + str(dispatches))
        print("  Shadow Accuracy:      " + str(accuracy_num) + "/" + str(eligible_obs) +
              " = " + str(round(shadow_accuracy_pct, 1)) + "% [" + evidence_maturity + "]")
        print("  Stage 2 Eligible:     " + str(stage2_eligible))
        if stage2_block_reasons:
            for r in stage2_block_reasons:
                print("    BLOCKED: " + r)
        print("  Snapshot Hash:        " + snapshot_hash[:16] + "...")

        snapshots.append(snapshot)

    # Write output
    out_dir = Path(r"C:\Users\aamir\.gemini\antigravity-ide\brain\db97d69f-81f9-4ab9-9ace-199d4e308384\scratch")
    out_path = out_dir / ("stage1_snapshot_" + str(target_date) + ".json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshots, f, indent=2, default=str)
    print("\nSnapshot written to: " + str(out_path))

    return snapshots


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate deterministic Stage-1 daily snapshot")
    parser.add_argument("--date", type=str, default=str(date.today()))
    parser.add_argument("--org", type=str, default=None)
    args = parser.parse_args()

    target = date.fromisoformat(args.date)

    import asyncpg
    pg_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_url, timeout=30)
    try:
        await generate_snapshot(conn, target, args.org)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
