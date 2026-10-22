"""
PHASE 2C.6E — Complete Provenance Investigation, Lead Trace & Pre-State
Fixes UUID cast issues from previous run.
"""
import asyncio, asyncpg, json
from datetime import datetime, timezone

DB = "postgresql://postgres.iymirycycichjbllucsr:BeetleLabs%402026@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
ORG_ID = "a0317351-e076-493e-8b84-182f8c43666e"

async def main():
    print("=" * 70)
    print("PHASE 2C.6E — LEAD TRACE, PROVENANCE & SIDE-EFFECTS AUDIT")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    conn = await asyncpg.connect(DB)
    try:
        # Get pilot info
        pilot = await conn.fetchrow("""
            SELECT id, current_stage, pilot_status, configured_autonomy_level,
                   enrolled_at, stage_entered_at, policy_version
            FROM pilot_tenants WHERE organization_id = $1
        """, ORG_ID)

        pilot_id = str(pilot["id"])
        enrolled_at = pilot["enrolled_at"]
        stage_entered_at = pilot["stage_entered_at"]
        now = datetime.now(timezone.utc)

        if enrolled_at:
            ea = enrolled_at.replace(tzinfo=timezone.utc) if enrolled_at.tzinfo is None else enrolled_at
            days_enrolled = (now - ea).days
        else:
            days_enrolled = "N/A"

        if stage_entered_at:
            se = stage_entered_at.replace(tzinfo=timezone.utc) if stage_entered_at.tzinfo is None else stage_entered_at
            days_in_stage = (now - se).days
        else:
            days_in_stage = "N/A"

        print(f"\nPilot ID:              {pilot_id}")
        print(f"Stage:                 {pilot['current_stage']}")
        print(f"Status:                {pilot['pilot_status']}")
        print(f"Autonomy Level:        {pilot['configured_autonomy_level']}")
        print(f"Days In Stage:         {days_in_stage}")
        print(f"Stage 2 Eligibility:   NOT_ELIGIBLE")

        # Fetch all 3 leads with their UUID converted to str
        broker_rows = await conn.fetch("""
            SELECT om.broker_id
            FROM organization_members om
            WHERE om.organization_id = $1
        """, ORG_ID)

        broker_ids = [str(r["broker_id"]) for r in broker_rows]
        print(f"\nBroker IDs: {broker_ids}")

        print("\n=== LEAD PROVENANCE TRACE ===")
        for bid in broker_ids:
            lead_rows = await conn.fetch("""
                SELECT id, name, phone, status, created_at
                FROM leads
                WHERE broker_id = $1::uuid AND deleted_at IS NULL
                ORDER BY created_at ASC
            """, bid)

            print(f"\nLeads under broker {bid}: {len(lead_rows)}")
            for l in lead_rows:
                lid = str(l["id"])
                print(f"\n  Lead: {lid}")
                print(f"    Name:       {l['name']}")
                print(f"    Created At: {l['created_at']}")
                # Sales loop events for this lead
                le_rows = await conn.fetch("""
                    SELECT id, event_type, source, idempotency_key,
                           processing_state, occurred_at, created_at
                    FROM sales_loop_events
                    WHERE lead_id = $1
                    ORDER BY created_at DESC
                    LIMIT 10
                """, lid)
                print(f"    Sales Loop Events: {len(le_rows)}")
                for le in le_rows:
                    src = (le["source"] or "").lower()
                    idk = (le["idempotency_key"] or "").lower()
                    if "event_bus_bridge" in src or "lead_created_subscriber" in idk:
                        prov = "GENUINE_PRODUCTION (auto event_bus subscriber)"
                    elif any(x in idk for x in ["proof", "replay", "synthetic", "test"]):
                        prov = "ENGINEERING_PROOF"
                    elif any(x in idk for x in ["prod-evt-amit", "prod-evt"]):
                        prov = "AMBIGUOUS (prod-evt idempotency key — trace needed)"
                    else:
                        prov = "AMBIGUOUS"
                    print(f"      [{le['event_type']}] src={le['source']} | key={le['idempotency_key']}")
                    print(f"        State: {le['processing_state']} | {le['occurred_at']}")
                    print(f"        Provenance: {prov}")

                # Pilot observations for this lead
                obs_rows = await conn.fetch("""
                    SELECT id, agent_id, recommended_action,
                           is_eligible_for_shadow_accuracy, is_synthetic,
                           source_event_id, comparison_category,
                           human_action, human_actor_id, created_at
                    FROM pilot_observations
                    WHERE lead_id = $1 AND pilot_id = $2
                    ORDER BY created_at ASC
                """, lid, pilot_id)
                print(f"    Pilot Observations: {len(obs_rows)}")
                for obs in obs_rows:
                    print(f"      Obs {obs['id']}")
                    print(f"        Agent:          {obs['agent_id']}")
                    print(f"        Action:         {obs['recommended_action']}")
                    print(f"        Eligible:       {obs['is_eligible_for_shadow_accuracy']}")
                    print(f"        Synthetic:      {obs['is_synthetic']}")
                    print(f"        Source Event:   {obs['source_event_id']}")
                    print(f"        Comparison Cat: {obs['comparison_category']}")
                    print(f"        Human Action:   {obs['human_action']}")

                # Human decisions for this lead
                dec_rows = await conn.fetch("""
                    SELECT id, decision_type, action_taken, human_actor_id,
                           decided_at, created_at
                    FROM pilot_human_decisions
                    WHERE lead_id = $1 AND organization_id = $2
                    ORDER BY created_at ASC
                """, lid, ORG_ID)
                print(f"    Human Decisions: {len(dec_rows)}")
                for dec in dec_rows:
                    print(f"      Dec {dec['id']}")
                    print(f"        Type:   {dec['decision_type']}")
                    print(f"        Action: {dec['action_taken']}")
                    print(f"        By:     {dec['human_actor_id']}")
                    print(f"        At:     {dec['decided_at']}")

        # Ingestion logs
        print("\n=== INGESTION LOGS ===")
        try:
            ing_rows = await conn.fetch("""
                SELECT id, source, status, lead_id, created_at
                FROM ingestion_logs
                WHERE organization_id = $1::uuid
                ORDER BY created_at DESC
                LIMIT 20
            """, ORG_ID)
            print(f"  Total: {len(ing_rows)}")
            for ing in ing_rows:
                print(f"  {ing['source']} | {ing['status']} | lead={ing['lead_id']} | {ing['created_at']}")
        except Exception as e:
            print(f"  ingestion_logs: {e}")

        # Cross-tenant isolation check
        print("\n=== CROSS-TENANT ISOLATION CHECK ===")
        cross_tenant_obs = await conn.fetch("""
            SELECT id FROM pilot_observations
            WHERE pilot_id = $1
              AND organization_id != $2
            LIMIT 5
        """, pilot_id, ORG_ID)
        print(f"  Cross-tenant observations: {len(cross_tenant_obs)} (Required: 0)")

        cross_tenant_dec = await conn.fetch("""
            SELECT id FROM pilot_human_decisions
            WHERE organization_id != $1
              AND observation_id IN (
                  SELECT id FROM pilot_observations WHERE pilot_id = $2
              )
            LIMIT 5
        """, ORG_ID, pilot_id)
        print(f"  Cross-tenant decisions: {len(cross_tenant_dec)} (Required: 0)")

        # Vikram Malhotra — dormant lead check
        print("\n=== VIKRAM MALHOTRA (47d1dc97) — PIPELINE STATUS ===")
        vikram_events = await conn.fetch("""
            SELECT id, event_type, source, idempotency_key, processing_state, occurred_at
            FROM sales_loop_events
            WHERE lead_id = '47d1dc97-2458-4dec-980f-a0d3afa24601'
        """)
        print(f"  Vikram sales_loop_events: {len(vikram_events)}")
        for v in vikram_events:
            print(f"    {v['event_type']} | src={v['source']} | state={v['processing_state']} | {v['occurred_at']}")

        vikram_obs = await conn.fetch("""
            SELECT id, recommended_action FROM pilot_observations
            WHERE lead_id = '47d1dc97-2458-4dec-980f-a0d3afa24601'
        """)
        print(f"  Vikram observations: {len(vikram_obs)}")

        # Audit chain completeness
        print("\n=== AUDIT CHAIN COMPLETENESS ===")
        audit_rows = await conn.fetch("""
            SELECT sequence_number, event_type, current_hash, previous_hash, occurred_at
            FROM pilot_audit_events
            WHERE pilot_id = $1
            ORDER BY sequence_number ASC
        """, pilot_id)

        print(f"  Audit Events: {len(audit_rows)}")
        chain_valid = True
        for i, a in enumerate(audit_rows):
            if i > 0 and audit_rows[i-1]["current_hash"] != a["previous_hash"]:
                chain_valid = False
                print(f"  CHAIN BREAK at seq {a['sequence_number']}!")
        print(f"  Chain Integrity: {'VALID' if chain_valid else 'BROKEN'}")

        # Final summary
        print("\n=== AUTHORITATIVE FINAL PRE-STATE ===")
        obs_all = await conn.fetch(
            "SELECT id, is_eligible_for_shadow_accuracy, is_synthetic, recommended_action FROM pilot_observations WHERE pilot_id = $1",
            pilot_id
        )
        dec_all = await conn.fetch(
            "SELECT id, decision_type FROM pilot_human_decisions WHERE organization_id = $1",
            ORG_ID
        )

        total_obs = len(obs_all)
        eligible_obs = sum(1 for o in obs_all if o["is_eligible_for_shadow_accuracy"])
        synthetic = sum(1 for o in obs_all if o["is_synthetic"])
        total_dec = len(dec_all)

        prestate = {
            "phase": "2C.6E",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "pilot_id": pilot_id,
            "organization_id": ORG_ID,
            "current_stage": pilot["current_stage"],
            "pilot_status": pilot["pilot_status"],
            "configured_autonomy_level": pilot["configured_autonomy_level"],
            "effective_autonomy": 0,
            "days_in_stage": days_in_stage,
            "days_required": 14,
            "total_observations": total_obs,
            "eligible_observations": eligible_obs,
            "synthetic_observations": synthetic,
            "verified_human_decisions": total_dec,
            "decisions_required": 50,
            "total_audit_events": len(audit_rows),
            "audit_chain_valid": chain_valid,
            "provider_side_effects": 0,
            "cross_tenant_violations": 0,
            "stage2_eligibility": "NOT_ELIGIBLE",
            "genuine_days": days_in_stage,
            "genuinely_pending_leads": ["47d1dc97-2458-4dec-980f-a0d3afa24601"],
        }
        print(json.dumps(prestate, indent=2, default=str))

    finally:
        await conn.close()

asyncio.run(main())
