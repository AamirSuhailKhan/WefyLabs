import asyncio
import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('apps/api/.env')
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text

async def run_audit():
    url = os.environ.get('DATABASE_URL')
    engine = create_async_engine(url, poolclass=NullPool)
    
    async with engine.connect() as conn:
        print("=== 1. CURRENT DB TIMESTAMP & VERSION ===")
        ts_res = await conn.execute(text("SELECT CURRENT_TIMESTAMP, CURRENT_DATE"))
        now_ts, now_date = ts_res.fetchone()
        print(f"PostgreSQL NOW: {now_ts} (Date: {now_date})")

        print("\n=== 2. ACTIVE PILOT TENANTS ===")
        pilots = await conn.execute(text("""
            SELECT id, organization_id, pilot_status, current_stage, configured_autonomy_level, 
                   policy_version, enrolled_by, enrolled_at, stage_entered_at, enrolled_agent_ids, created_at, updated_at
            FROM pilot_tenants
        """))
        pilot_rows = pilots.fetchall()
        print(f"Total pilots: {len(pilot_rows)}")
        pilot_id = None
        org_id = None
        enrolled_at = None
        for p in pilot_rows:
            pilot_id = str(p[0])
            org_id = str(p[1])
            enrolled_at = p[7]
            print(f"  Pilot ID: {p[0]}")
            print(f"  Org ID: {p[1]}")
            print(f"  Status: {p[2]}")
            print(f"  Stage: {p[3]}")
            print(f"  Configured Autonomy: {p[4]}")
            print(f"  Policy Version: {p[5]}")
            print(f"  Enrolled By: {p[6]}")
            print(f"  Enrolled At: {p[7]}")
            print(f"  Agents Enrolled: {json.loads(p[9]) if isinstance(p[9], str) else p[9]}")
            print(f"  Updated At: {p[11]}")

        if enrolled_at:
            enroll_date = enrolled_at.date()
            curr_date = now_ts.date()
            elapsed_days = (curr_date - enroll_date).days + 1
            print(f"\n=== 3. PILOT CLOCK CALCULATION ===")
            print(f"Authoritative Enrolled At: {enrolled_at}")
            print(f"Current DB Timestamp: {now_ts}")
            print(f"Enroll Date: {enroll_date}, Current Date: {curr_date}")
            print(f"Elapsed Calendar Days: {elapsed_days} (Operational Days: D1={enroll_date}, D2={curr_date})")

        print("\n=== 4. RECORD COUNTS ACROSS PILOT & EVIDENCE TABLES ===")
        tables = [
            "pilot_tenants",
            "pilot_observations",
            "pilot_human_decisions",
            "pilot_audit_events",
            "pilot_metric_snapshots",
            "pilot_approval_items",
            "pilot_evidence_records",
            "pilot_stage_transitions",
            "pilot_cohort_guards",
            "leads",
            "lead_qualification",
            "lead_timeline_events",
            "communication_logs",
            "deals"
        ]
        counts = {}
        for t in tables:
            try:
                async with conn.begin_nested():
                    res = await conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
                    c = res.scalar()
                    counts[t] = c
                    print(f"  {t}: {c}")
            except Exception as e:
                print(f"  {t}: NOT FOUND ({e.orig if hasattr(e, 'orig') else e})")

        print("\n=== 5. OBSERVATIONS INTEGRITY ===")
        obs = await conn.execute(text("""
            SELECT id, pilot_id, organization_id, lead_id, agent_id, agent_version, 
                   policy_version, execution_mode, is_synthetic, recommended_action, 
                   comparison_category, agreement_score, created_at
            FROM pilot_observations
        """))
        obs_rows = obs.fetchall()
        print(f"Total observations: {len(obs_rows)}")
        for o in obs_rows:
            print(f"  Obs ID: {o[0]}")
            print(f"    Org ID: {o[2]}, Lead ID: {o[3]}")
            print(f"    Agent: {o[4]} (v{o[5]}), Policy: {o[6]}")
            print(f"    Mode: {o[7]}, Synthetic: {o[8]}")
            print(f"    Recommended Action: {o[9]}")
            print(f"    Comparison: {o[10]} (Score: {o[11]})")
            print(f"    Created At: {o[12]}")

        print("\n=== 6. HUMAN DECISIONS INTEGRITY ===")
        decs = await conn.execute(text("""
            SELECT id, organization_id, observation_id, lead_id, human_actor_id, human_actor_role, 
                   decision_type, action_taken, reason, decided_at, created_at
            FROM pilot_human_decisions
        """))
        dec_rows = decs.fetchall()
        print(f"Total human decisions: {len(dec_rows)}")
        for d in dec_rows:
            print(f"  Dec ID: {d[0]}")
            print(f"    Org ID: {d[1]}, Obs ID: {d[2]}, Lead ID: {d[3]}")
            print(f"    Actor: {d[4]} (Role: {d[5]})")
            print(f"    Decision Type: {d[6]}, Action Taken: {d[7]}")
            print(f"    Reason: {d[8]}")
            print(f"    Decided At: {d[9]}")

        print("\n=== 7. AUDIT HASH CHAIN ===")
        audits = await conn.execute(text("""
            SELECT id, event_type, current_hash, previous_hash, sequence_number, occurred_at
            FROM pilot_audit_events
            ORDER BY sequence_number ASC, occurred_at ASC
        """))
        audit_rows = audits.fetchall()
        print(f"Total audit events: {len(audit_rows)}")
        prev_hash = None
        broken_links = 0
        for idx, a in enumerate(audit_rows):
            print(f"  [{idx}] Seq: {a[4]} | ID: {a[0]} | Type: {a[1]}")
            print(f"        PrevHash: {a[3]}")
            print(f"        CurrHash: {a[2]}")
            if idx > 0 and a[3] != prev_hash:
                print(f"    WARNING: Chain break detected! Expected {prev_hash}, found {a[3]}")
                broken_links += 1
            prev_hash = a[2]
        print(f"Broken links: {broken_links}")

        print("\n=== 8. DAILY METRIC SNAPSHOTS ===")
        snaps = await conn.execute(text("""
            SELECT id, pilot_id, organization_id, stage, metric_name, metric_value, 
                   sample_size, period_start, period_end, source, is_synthetic, computed_at
            FROM pilot_metric_snapshots
            ORDER BY period_start ASC
        """))
        snap_rows = snaps.fetchall()
        print(f"Total snapshots: {len(snap_rows)}")
        for s in snap_rows:
            print(f"  Snap ID: {s[0]} | Metric: {s[4]} = {s[5]} (Sample: {s[6]})")
            print(f"    Stage: {s[3]} | Period: {s[7]} to {s[8]}")
            print(f"    Source: {s[9]} | Synthetic: {s[10]} | Computed At: {s[11]}")

        print("\n=== 9. RECONCILIATION SUMMARY ===")
        tot_obs = len(obs_rows)
        tot_decs = len(dec_rows)
        synth_obs = sum(1 for o in obs_rows if o[8])
        print(f"Actual DB Observations: {tot_obs}")
        print(f"Actual DB Human Decisions: {tot_decs}")
        print(f"Actual DB Synthetic Observations: {synth_obs}")

if __name__ == '__main__':
    asyncio.run(run_audit())
