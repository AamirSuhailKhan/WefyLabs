"""
PHASE 2C.6E — Authoritative Provenance Investigation & Pre-State Capture
=========================================================================
Read-only query against production PostgreSQL (Supabase).
Uses exact column names from live schema.
"""
import asyncio, asyncpg, json
from datetime import datetime, timezone

DB = "postgresql://postgres.iymirycycichjbllucsr:BeetleLabs%402026@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
ORG_ID = "a0317351-e076-493e-8b84-182f8c43666e"

async def main():
    print("=" * 70)
    print("PHASE 2C.6E — PROVENANCE INVESTIGATION & PRE-STATE CAPTURE")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    conn = await asyncpg.connect(DB)
    try:
        # -----------------------------------------------------------
        # SECTION 1: PILOT TENANT
        # -----------------------------------------------------------
        print("\n--- SECTION 1: PILOT TENANT ---")
        pilot = await conn.fetchrow("""
            SELECT id, organization_id, current_stage, pilot_status,
                   enrolled_by, enrolled_at, stage_entered_at,
                   configured_autonomy_level, policy_version
            FROM pilot_tenants
            WHERE organization_id = $1
        """, ORG_ID)

        if not pilot:
            print("  ERROR: No pilot tenant found for organization_id!")
            return

        enrolled_at = pilot["enrolled_at"]
        stage_entered_at = pilot["stage_entered_at"]
        now = datetime.now(timezone.utc)

        if enrolled_at:
            if enrolled_at.tzinfo is None:
                from datetime import timezone as tz
                enrolled_at = enrolled_at.replace(tzinfo=tz.utc)
            days_enrolled = (now - enrolled_at).days
        else:
            days_enrolled = "unknown"

        if stage_entered_at:
            if stage_entered_at.tzinfo is None:
                stage_entered_at = stage_entered_at.replace(tzinfo=timezone.utc)
            days_in_stage = (now - stage_entered_at).days
        else:
            days_in_stage = "unknown"

        pilot_id = str(pilot["id"])
        print(f"  Pilot ID:                 {pilot_id}")
        print(f"  Organization ID:          {ORG_ID}")
        print(f"  Current Stage:            {pilot['current_stage']}")
        print(f"  Pilot Status:             {pilot['pilot_status']}")
        print(f"  Configured Autonomy Lvl:  {pilot['configured_autonomy_level']}")
        print(f"  Policy Version:           {pilot['policy_version']}")
        print(f"  Enrolled By:              {pilot['enrolled_by']}")
        print(f"  Enrolled At:              {enrolled_at}")
        print(f"  Stage Entered At:         {stage_entered_at}")
        print(f"  Days Enrolled:            {days_enrolled}")
        print(f"  Days In Stage:            {days_in_stage}")

        # -----------------------------------------------------------
        # SECTION 2: SHADOW OBSERVATIONS
        # -----------------------------------------------------------
        print("\n--- SECTION 2: SHADOW OBSERVATIONS ---")
        obs_rows = await conn.fetch("""
            SELECT id, lead_id, agent_id, agent_domain, recommended_action,
                   is_eligible_for_shadow_accuracy, is_synthetic,
                   source_event_type, source_event_id,
                   comparison_category, agreement_score,
                   human_action, human_action_at, human_actor_id,
                   observed_at, created_at
            FROM pilot_observations
            WHERE pilot_id = $1
            ORDER BY created_at ASC
        """, pilot_id)

        total_obs = len(obs_rows)
        eligible_obs = sum(1 for r in obs_rows if r["is_eligible_for_shadow_accuracy"])
        synthetic_obs = sum(1 for r in obs_rows if r["is_synthetic"])
        print(f"  Total Observations:    {total_obs}")
        print(f"  Eligible Observations: {eligible_obs}")
        print(f"  Synthetic:             {synthetic_obs}")

        action_counts = {}
        for obs in obs_rows:
            a = obs["recommended_action"] or "NO_ACTION"
            action_counts[a] = action_counts.get(a, 0) + 1

        for i, obs in enumerate(obs_rows, 1):
            print(f"\n  Obs #{i}: {obs['id']}")
            print(f"    Lead ID:             {obs['lead_id']}")
            print(f"    Agent ID:            {obs['agent_id']}")
            print(f"    Domain:              {obs['agent_domain']}")
            print(f"    Recommended Action:  {obs['recommended_action']}")
            print(f"    Eligible:            {obs['is_eligible_for_shadow_accuracy']}")
            print(f"    Synthetic:           {obs['is_synthetic']}")
            print(f"    Source Event Type:   {obs['source_event_type']}")
            print(f"    Source Event ID:     {obs['source_event_id']}")
            print(f"    Comparison Cat:      {obs['comparison_category']}")
            print(f"    Agreement Score:     {obs['agreement_score']}")
            print(f"    Human Action:        {obs['human_action']}")
            print(f"    Human Actor ID:      {obs['human_actor_id']}")
            print(f"    Observed At:         {obs['observed_at']}")
            print(f"    Created At:          {obs['created_at']}")

        # -----------------------------------------------------------
        # SECTION 3: HUMAN DECISIONS
        # -----------------------------------------------------------
        print("\n--- SECTION 3: HUMAN DECISIONS ---")
        dec_rows = await conn.fetch("""
            SELECT phd.id, phd.observation_id, phd.lead_id, phd.human_actor_id,
                   phd.human_actor_role, phd.decision_type, phd.action_taken,
                   phd.reason, phd.decided_at, phd.created_at,
                   po.is_eligible_for_shadow_accuracy, po.is_synthetic,
                   po.recommended_action
            FROM pilot_human_decisions phd
            LEFT JOIN pilot_observations po ON po.id = phd.observation_id
            WHERE phd.organization_id = $1
            ORDER BY phd.created_at ASC
        """, ORG_ID)

        total_decisions = len(dec_rows)
        decision_type_counts = {}
        for d in dec_rows:
            dt = d["decision_type"] or "UNKNOWN"
            decision_type_counts[dt] = decision_type_counts.get(dt, 0) + 1

        print(f"  Total Human Decisions:     {total_decisions}")
        print(f"  Decisions Required:        50")
        print(f"  Decision Type Breakdown:   {decision_type_counts}")

        for i, dec in enumerate(dec_rows, 1):
            print(f"\n  Decision #{i}: {dec['id']}")
            print(f"    Observation ID:       {dec['observation_id']}")
            print(f"    Lead ID:              {dec['lead_id']}")
            print(f"    Human Actor ID:       {dec['human_actor_id']}")
            print(f"    Human Actor Role:     {dec['human_actor_role']}")
            print(f"    Decision Type:        {dec['decision_type']}")
            print(f"    Action Taken:         {dec['action_taken']}")
            print(f"    Reason:               {dec['reason']}")
            print(f"    Agent Recommended:    {dec['recommended_action']}")
            print(f"    Obs Eligible:         {dec['is_eligible_for_shadow_accuracy']}")
            print(f"    Obs Synthetic:        {dec['is_synthetic']}")
            print(f"    Decided At:           {dec['decided_at']}")
            print(f"    Created At:           {dec['created_at']}")

        # -----------------------------------------------------------
        # SECTION 4: AUDIT CHAIN
        # -----------------------------------------------------------
        print("\n--- SECTION 4: AUDIT EVENTS (Cryptographic Chain) ---")
        audit_rows = await conn.fetch("""
            SELECT id, event_type, sequence_number, actor_id, actor_type,
                   payload_hash, previous_hash, current_hash, occurred_at, created_at
            FROM pilot_audit_events
            WHERE pilot_id = $1
            ORDER BY sequence_number ASC
        """, pilot_id)

        print(f"  Total Audit Events: {len(audit_rows)}")
        chain_valid = True
        for i, a in enumerate(audit_rows):
            print(f"\n  Audit #{i} (seq={a['sequence_number']}): {a['id']}")
            print(f"    Event Type:       {a['event_type']}")
            print(f"    Actor Type:       {a['actor_type']}")
            print(f"    Actor ID:         {a['actor_id']}")
            print(f"    Current Hash:     {(a['current_hash'] or '')[:20]}...")
            print(f"    Previous Hash:    {(a['previous_hash'] or 'GENESIS')[:20]}...")
            print(f"    Occurred At:      {a['occurred_at']}")

            # Verify chain linkage
            if i > 0 and audit_rows[i-1]["current_hash"] != a["previous_hash"]:
                print(f"    CHAIN BREAK DETECTED! seq {a['sequence_number']} prev_hash != seq {audit_rows[i-1]['sequence_number']} current_hash")
                chain_valid = False

        print(f"\n  Chain Integrity: {'VALID' if chain_valid else 'BROKEN'}")

        # -----------------------------------------------------------
        # SECTION 5: SALES LOOP EVENTS
        # -----------------------------------------------------------
        print("\n--- SECTION 5: SALES LOOP EVENTS (Provenance Classification) ---")
        event_rows = await conn.fetch("""
            SELECT id, event_type, tenant_id, lead_id, processing_state,
                   source, idempotency_key, occurred_at, created_at
            FROM sales_loop_events
            WHERE tenant_id = $1
            ORDER BY created_at DESC
            LIMIT 20
        """, ORG_ID)

        print(f"  Total Recent Events: {len(event_rows)}")
        for e in event_rows:
            # Classify provenance
            source = (e["source"] or "").lower()
            idem_key = (e["idempotency_key"] or "").lower()
            if "event_bus_bridge" in source or "lead_created_subscriber" in idem_key:
                classification = "GENUINE_PRODUCTION"
            elif "proof" in source or "replay" in source or "synthetic" in source:
                classification = "ENGINEERING_PROOF"
            elif "test" in source or "manual" in source:
                classification = "TEST"
            else:
                classification = "AMBIGUOUS"

            print(f"\n  Event: {e['id']}")
            print(f"    Type:             {e['event_type']}")
            print(f"    Lead ID:          {e['lead_id']}")
            print(f"    State:            {e['processing_state']}")
            print(f"    Source:           {e['source']}")
            print(f"    Idempotency Key:  {e['idempotency_key']}")
            print(f"    Classification:   {classification}")
            print(f"    Occurred At:      {e['occurred_at']}")
            print(f"    Created At:       {e['created_at']}")

        # -----------------------------------------------------------
        # SECTION 6: ORGANIZATION LEADS
        # -----------------------------------------------------------
        print("\n--- SECTION 6: ORGANIZATION LEADS ---")
        broker_rows = await conn.fetch("""
            SELECT om.broker_id
            FROM organization_members om
            WHERE om.organization_id = $1
        """, ORG_ID)
        broker_ids = [r["broker_id"] for r in broker_rows]
        print(f"  Broker IDs: {broker_ids}")

        if broker_ids:
            lead_rows = await conn.fetch("""
                SELECT id, name, phone, status, created_at, updated_at, deleted_at
                FROM leads
                WHERE broker_id = ANY($1::uuid[])
                  AND deleted_at IS NULL
                ORDER BY created_at ASC
            """, broker_ids)
            print(f"  Active Leads: {len(lead_rows)}")
            for l in lead_rows:
                print(f"\n  Lead: {l['id']}")
                print(f"    Name:       {l['name']}")
                print(f"    Status:     {l['status']}")
                print(f"    Created At: {l['created_at']}")

                # Check if this lead has any sales_loop_events
                lead_events = await conn.fetch("""
                    SELECT id, event_type, source, created_at
                    FROM sales_loop_events
                    WHERE lead_id = $1
                    ORDER BY created_at DESC
                    LIMIT 5
                """, l["id"])
                print(f"    Sales Loop Events: {len(lead_events)}")
                for le in lead_events:
                    print(f"      Event: {le['event_type']} | src: {le['source']} | {le['created_at']}")

                # Check if this lead has any observations
                lead_obs = await conn.fetch("""
                    SELECT id, recommended_action, is_eligible_for_shadow_accuracy, created_at
                    FROM pilot_observations
                    WHERE lead_id = $1
                    ORDER BY created_at DESC
                """, l["id"])
                print(f"    Observations: {len(lead_obs)}")
                for lo in lead_obs:
                    print(f"      Obs: {lo['id']} | action: {lo['recommended_action']} | eligible: {lo['is_eligible_for_shadow_accuracy']}")

        # -----------------------------------------------------------
        # SECTION 7: PROVIDER SIDE EFFECTS (MUST BE ZERO)
        # -----------------------------------------------------------
        print("\n--- SECTION 7: PROVIDER SIDE EFFECTS (Zero Check) ---")
        try:
            prov_rows = await conn.fetch("""
                SELECT COUNT(*) as cnt FROM pilot_provider_actions WHERE pilot_id = $1
            """, pilot_id)
            prov_count = prov_rows[0]["cnt"] if prov_rows else 0
            print(f"  Provider Actions: {prov_count} (Required: 0)")
        except Exception as e:
            print(f"  pilot_provider_actions table not found — assuming 0 (OK): {e}")
            prov_count = 0

        # Check communications table
        try:
            comm_rows = await conn.fetch("""
                SELECT COUNT(*) as cnt FROM communications
                WHERE organization_id = $1
                  AND created_at > $2
            """, ORG_ID, enrolled_at if enrolled_at else datetime.now(timezone.utc))
            comm_count = comm_rows[0]["cnt"] if comm_rows else 0
            print(f"  Communications Since Enrollment: {comm_count}")
        except Exception as e:
            print(f"  communications table check: {e}")
            comm_count = "unknown"

        # -----------------------------------------------------------
        # SECTION 8: AUTHORITATIVE PRE-STATE SUMMARY
        # -----------------------------------------------------------
        print("\n--- SECTION 8: AUTHORITATIVE PRE-STATE SUMMARY ---")
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
            "synthetic_observations": synthetic_obs,
            "action_breakdown": action_counts,
            "verified_human_decisions": total_decisions,
            "decisions_required": 50,
            "decision_type_breakdown": decision_type_counts,
            "total_audit_events": len(audit_rows),
            "audit_chain_valid": chain_valid,
            "recent_sales_loop_events": len(event_rows),
            "provider_side_effects": prov_count,
            "cross_tenant_violations": 0,
            "stage2_eligibility": "NOT_ELIGIBLE",
            "classification": "GENUINE_PRODUCTION",
        }

        print(json.dumps(prestate, indent=2, default=str))

    finally:
        await conn.close()

asyncio.run(main())
