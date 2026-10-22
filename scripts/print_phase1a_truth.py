import asyncio
import os
import json
from datetime import datetime
import asyncpg

env_path = r"C:\Users\aamir\OneDrive\Desktop\crm real state\apps\api\.env"
with open(env_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    org_id = "a0317351-e076-493e-8b84-182f8c43666e"
    pilot_id = "d153ea17-b2d3-40ab-b258-75951ef7de28"

    print("=" * 80)
    print("PHASE 1A — AUTHORITATIVE DATABASE TRUTH")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 80)

    print("\n=== 1. ALL LEADS FOR PILOT ORGANIZATION ===")
    leads = await conn.fetch(
        "SELECT id, organization_id, broker_id, name, email, phone, status, created_at, updated_at "
        "FROM leads WHERE organization_id = $1 ORDER BY created_at DESC",
        org_id
    )
    print(f"Total count: {len(leads)}")
    for l in leads:
        print(json.dumps({k: str(v) if v is not None else None for k, v in dict(l).items()}, indent=2))

    print("\n=== 2. ALL SALES_LOOP_EVENTS FOR PILOT ORGANIZATION ===")
    events = await conn.fetch(
        "SELECT id, idempotency_key, event_type, schema_version, tenant_id, lead_id, broker_id, correlation_id, "
        "processing_state, retry_count, last_error, failure_class, source, occurred_at, processing_started_at, "
        "processing_completed_at, created_at "
        "FROM sales_loop_events WHERE tenant_id = $1 ORDER BY created_at DESC",
        org_id
    )
    print(f"Total count: {len(events)}")
    for e in events:
        print(json.dumps({k: str(v) if v is not None else None for k, v in dict(e).items()}, indent=2))

    print("\n=== 3. ALL PILOT_OBSERVATIONS FOR PILOT ===")
    obs = await conn.fetch(
        "SELECT id, pilot_id, organization_id, lead_id, agent_id, agent_domain, agent_version, execution_id, "
        "source_event_id, source_event_type, recommended_action, recommended_action_reasoning, agent_confidence, "
        "policy_decision, human_action, human_action_at, human_actor_id, comparison_category, agreement_score, "
        "is_eligible_for_shadow_accuracy, is_synthetic, execution_mode, pilot_stage, observed_at, created_at "
        "FROM pilot_observations WHERE pilot_id = $1 ORDER BY created_at DESC",
        pilot_id
    )
    print(f"Total count: {len(obs)}")
    for o in obs:
        print(json.dumps({k: str(v) if v is not None else None for k, v in dict(o).items()}, indent=2))

    print("\n=== 4. ALL PILOT_HUMAN_DECISIONS FOR PILOT ===")
    decs = await conn.fetch(
        "SELECT id, observation_id, organization_id, lead_id, human_actor_id, human_actor_role, decision_type, "
        "action_taken, reason, decided_at, created_at "
        "FROM pilot_human_decisions WHERE organization_id = $1 ORDER BY created_at DESC",
        org_id
    )
    print(f"Total count: {len(decs)}")
    for d in decs:
        print(json.dumps({k: str(v) if v is not None else None for k, v in dict(d).items()}, indent=2))

    print("\n=== 5. ALL PILOT_AUDIT_EVENTS FOR PILOT ===")
    audits = await conn.fetch(
        "SELECT id, pilot_id, organization_id, event_type, actor_type, actor_id, sequence_number, current_hash, "
        "previous_hash, payload_hash, occurred_at "
        "FROM pilot_audit_events WHERE pilot_id = $1 ORDER BY sequence_number ASC",
        pilot_id
    )
    print(f"Total count: {len(audits)}")
    for a in audits:
        print(json.dumps({k: str(v) if v is not None else None for k, v in dict(a).items()}, indent=2))

    print("\n=== 6. ALL PILOT_METRIC_SNAPSHOTS FOR PILOT ===")
    snaps = await conn.fetch(
        "SELECT * FROM pilot_metric_snapshots WHERE pilot_id = $1 ORDER BY created_at DESC",
        pilot_id
    )
    print(f"Total count: {len(snaps)}")
    for s in snaps:
        print(json.dumps({k: str(v) if v is not None else None for k, v in dict(s).items()}, indent=2))

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
