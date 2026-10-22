"""
Phase 2C.6E — Production State Investigation Script (Fixed & Robust)
===================================================================
1. Connects to production DB (Supabase via asyncpg)
2. Reads pilot tenant state
3. Reads lead ingestion events from queue/DB
4. Reads pilot observations table
5. Reads pilot human decisions
6. Inspects sales_loop_events structure and rows
7. Traces recent leads
8. Reads pilot audit events
9. Captures counts and summary stats

Robust error handling per section with auto-rollback. No non-ASCII characters in stdout.
"""
import asyncio
import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'api'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'apps', 'api', '.env'))

os.environ.setdefault('ENV', 'development')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = os.environ['DATABASE_URL']
if DATABASE_URL.startswith('postgresql+asyncpg://'):
    ASYNC_URL = DATABASE_URL
elif DATABASE_URL.startswith('postgresql://'):
    ASYNC_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://', 1)
else:
    ASYNC_URL = DATABASE_URL

engine = create_async_engine(ASYNC_URL, echo=False, pool_pre_ping=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def run():
    report = {}
    print("=== PHASE 2C.6E - PRODUCTION STATE INVESTIGATION ===")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()

    # 1. Pilot tenants
    print("--- 1. PILOT TENANTS ---")
    async with async_session() as db:
        try:
            res = await db.execute(text("""
                SELECT id, organization_id, pilot_status, current_stage,
                       configured_autonomy_level, enrolled_at, stage_entered_at,
                       enrolled_by, policy_version
                FROM pilot_tenants
                ORDER BY enrolled_at DESC
                LIMIT 20
            """))
            rows = res.fetchall()
            pilot_data = []
            for r in rows:
                row_dict = dict(r._mapping)
                pilot_data.append(row_dict)
                print(f"  Pilot ID: {row_dict['id']}")
                print(f"    org_id: {row_dict['organization_id']}")
                print(f"    status: {row_dict['pilot_status']} | stage: {row_dict['current_stage']}")
                print(f"    autonomy: {row_dict['configured_autonomy_level']}")
                print(f"    enrolled_at: {row_dict['enrolled_at']}")
                print(f"    stage_entered_at: {row_dict['stage_entered_at']}")
                print(f"    enrolled_by: {row_dict['enrolled_by']}")
                print()
            report['pilot_tenants'] = pilot_data
        except Exception as e:
            print(f"  ERROR: {e}")
            report['pilot_tenants'] = {'error': str(e)}

    # 2. Pilot observations
    print("--- 2. PILOT OBSERVATIONS (all) ---")
    async with async_session() as db:
        try:
            res = await db.execute(text("""
                SELECT id, organization_id, lead_id, agent_id, source_event_type,
                       recommended_action, pilot_stage, execution_mode,
                       is_synthetic, is_eligible_for_shadow_accuracy,
                       human_action, human_action_at, comparison_category,
                       observed_at
                FROM pilot_observations
                ORDER BY observed_at DESC
            """))
            rows = res.fetchall()
            obs_data = []
            for r in rows:
                row_dict = dict(r._mapping)
                obs_data.append(row_dict)
                print(f"  OBS [{str(row_dict['id'])[:8]}...]:")
                print(f"    org: {row_dict['organization_id']}")
                print(f"    lead: {row_dict['lead_id']}")
                print(f"    event: {row_dict['source_event_type']} -> action: {row_dict['recommended_action']}")
                print(f"    stage: {row_dict['pilot_stage']} | mode: {row_dict['execution_mode']}")
                print(f"    synthetic: {row_dict['is_synthetic']} | eligible: {row_dict['is_eligible_for_shadow_accuracy']}")
                print(f"    human_action: {row_dict['human_action']} at {row_dict['human_action_at']}")
                print(f"    comparison: {row_dict['comparison_category']}")
                print(f"    observed_at: {row_dict['observed_at']}")
                print()
            print(f"  Total observations found: {len(obs_data)}")
            report['pilot_observations'] = obs_data
        except Exception as e:
            print(f"  ERROR: {e}")
            report['pilot_observations'] = {'error': str(e)}

    # 3. Human decisions
    print("--- 3. PILOT HUMAN DECISIONS (all) ---")
    async with async_session() as db:
        try:
            res = await db.execute(text("""
                SELECT id, observation_id, organization_id, lead_id,
                       human_actor_id, human_actor_role, decision_type,
                       action_taken, reason, decided_at
                FROM pilot_human_decisions
                ORDER BY decided_at DESC
            """))
            rows = res.fetchall()
            dec_data = []
            for r in rows:
                row_dict = dict(r._mapping)
                dec_data.append(row_dict)
                print(f"  DECISION [{str(row_dict['id'])[:8]}...]:")
                print(f"    obs_id: {row_dict['observation_id']}")
                print(f"    org: {row_dict['organization_id']}")
                print(f"    lead: {row_dict['lead_id']}")
                print(f"    actor: {row_dict['human_actor_id']} ({row_dict['human_actor_role']})")
                print(f"    decision: {row_dict['decision_type']} -> {row_dict['action_taken']}")
                print(f"    decided_at: {row_dict['decided_at']}")
                print()
            print(f"  Total human decisions found: {len(dec_data)}")
            report['pilot_human_decisions'] = dec_data
        except Exception as e:
            print(f"  ERROR: {e}")
            report['pilot_human_decisions'] = {'error': str(e)}

    # 4. Check tables in schema
    print("--- 4. EVENT / AUDIT TABLES CHECK ---")
    async with async_session() as db:
        try:
            res = await db.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                  AND (table_name LIKE '%pilot%' OR table_name LIKE '%loop%' OR table_name LIKE '%event%' OR table_name LIKE '%lead%')
                ORDER BY table_name
            """))
            tables = [r[0] for r in res.fetchall()]
            print(f"  Relevant tables: {tables}")
            report['relevant_tables'] = tables
        except Exception as e:
            print(f"  ERROR: {e}")
            report['relevant_tables'] = {'error': str(e)}

    # 5. Leads table — get recent leads
    print("--- 5. RECENT LEADS (last 10) ---")
    async with async_session() as db:
        try:
            res = await db.execute(text("""
                SELECT id, organization_id, name, email, phone, status,
                       source, created_at, updated_at
                FROM leads
                ORDER BY created_at DESC
                LIMIT 10
            """))
            rows = res.fetchall()
            leads_data = []
            for r in rows:
                row_dict = dict(r._mapping)
                leads_data.append(row_dict)
                print(f"  LEAD [{row_dict['id']}]:")
                print(f"    org: {row_dict['organization_id']}")
                print(f"    name: {row_dict['name']} | status: {row_dict['status']}")
                print(f"    source: {row_dict['source']}")
                print(f"    created_at: {row_dict['created_at']}")
                print()
            report['recent_leads'] = leads_data
        except Exception as e:
            print(f"  ERROR: {e}")
            report['recent_leads'] = {'error': str(e)}

    # 6. Pilot audit events
    print("--- 6. PILOT AUDIT EVENTS (last 10) ---")
    async with async_session() as db:
        try:
            res = await db.execute(text("""
                SELECT id, organization_id, event_type, actor_type, actor_id,
                       occurred_at, payload
                FROM pilot_audit_events
                ORDER BY occurred_at DESC
                LIMIT 10
            """))
            rows = res.fetchall()
            audit_data = []
            for r in rows:
                row_dict = dict(r._mapping)
                payload_str = str(row_dict.get('payload', ''))[:120]
                audit_data.append(row_dict)
                print(f"  AUDIT [{str(row_dict['id'])[:8]}...]:")
                print(f"    org: {row_dict['organization_id']}")
                print(f"    event: {row_dict['event_type']} | actor: {row_dict['actor_type']} / {row_dict['actor_id']}")
                print(f"    occurred_at: {row_dict['occurred_at']}")
                print(f"    payload: {payload_str}")
                print()
            report['pilot_audit_events'] = audit_data
        except Exception as e:
            print(f"  ERROR: {e}")
            report['pilot_audit_events'] = {'error': str(e)}

    # 7. Pilot action records (checking for provider side-effects)
    print("--- 7. PILOT ACTION RECORDS (Provider Side Effects Check) ---")
    async with async_session() as db:
        try:
            res = await db.execute(text("""
                SELECT id, organization_id, lead_id, action_type, risk_class,
                       semantic_state, pilot_stage, execution_mode,
                       provider_name, provider_status, requested_at, executed_at
                FROM pilot_action_records
                ORDER BY requested_at DESC
                LIMIT 20
            """))
            rows = res.fetchall()
            actions_data = []
            for r in rows:
                row_dict = dict(r._mapping)
                actions_data.append(row_dict)
                print(f"  ACTION [{str(row_dict['id'])[:8]}...]:")
                print(f"    lead: {row_dict['lead_id']} | type: {row_dict['action_type']}")
                print(f"    state: {row_dict['semantic_state']} | stage: {row_dict['pilot_stage']}")
                print(f"    provider: {row_dict['provider_name']} | status: {row_dict['provider_status']}")
                print()
            print(f"  Total action records retrieved: {len(actions_data)}")
            report['pilot_action_records'] = actions_data
        except Exception as e:
            print(f"  ERROR: {e}")
            report['pilot_action_records'] = {'error': str(e)}

    # 8. Summary statistics
    print("--- 8. SUMMARY STATISTICS ---")
    async with async_session() as db:
        try:
            # Days in stage
            day_res = await db.execute(text("""
                SELECT id, organization_id, current_stage, stage_entered_at,
                       ROUND(CAST(EXTRACT(EPOCH FROM (NOW() - stage_entered_at)) / 86400 AS numeric), 2) AS days_in_stage
                FROM pilot_tenants
                WHERE pilot_status = 'ACTIVE'
            """))
            pilot_tenants_summary = [dict(r._mapping) for r in day_res.fetchall()]
            for pt in pilot_tenants_summary:
                print(f"  Tenant {pt['organization_id']}: stage={pt['current_stage']}, days_in_stage={pt['days_in_stage']}")

            # Genuine days calculation from daily snapshots or evidence
            # Check if pilot_metric_snapshots exists
            snap_res = await db.execute(text("""
                SELECT COUNT(DISTINCT DATE(snapshot_time)) as snapshot_days
                FROM pilot_metric_snapshots
            """))
            snap_days = snap_res.scalar() or 0
            print(f"  Snapshot distinct calendar days: {snap_days}")

            # Counts
            obs_cnt_res = await db.execute(text("SELECT is_synthetic, COUNT(*) FROM pilot_observations GROUP BY is_synthetic"))
            obs_counts = {str(r[0]): r[1] for r in obs_cnt_res.fetchall()}
            
            dec_cnt_res = await db.execute(text("SELECT COUNT(*) FROM pilot_human_decisions"))
            dec_count = dec_cnt_res.scalar() or 0

            actions_cnt_res = await db.execute(text("""
                SELECT semantic_state, COUNT(*) 
                FROM pilot_action_records 
                GROUP BY semantic_state
            """))
            actions_by_state = {r[0]: r[1] for r in actions_cnt_res.fetchall()}

            print(f"  Observations: real={obs_counts.get('False', 0)}, synthetic={obs_counts.get('True', 0)}")
            print(f"  Human decisions: {dec_count}")
            print(f"  Action record states: {actions_by_state}")

            report['summary'] = {
                'pilot_tenants': pilot_tenants_summary,
                'observations_real': obs_counts.get('False', 0),
                'observations_synthetic': obs_counts.get('True', 0),
                'human_decisions': dec_count,
                'snapshot_days': snap_days,
                'action_record_states': actions_by_state,
            }
        except Exception as e:
            print(f"  ERROR: {e}")
            report['summary'] = {'error': str(e)}

    # Save JSON report
    output_path = os.path.join(os.path.dirname(__file__), 'phase2c6e_production_state.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to: {output_path}")


if __name__ == '__main__':
    asyncio.run(run())
