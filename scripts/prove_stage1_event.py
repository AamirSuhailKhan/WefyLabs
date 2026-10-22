#!/usr/bin/env python3
"""
scripts/prove_stage1_event.py
==============================
PHASE 2C.6A — Live Stage-1 Evidence Forensic Tool

Accepts: event_id, decision_id, observation_id, or lead_id
Prints complete provenance chain:
  lead -> observation -> decision -> audit -> provider side effects

This is the canonical forensic tool for all future checkpoints.
Usage:
  python scripts/prove_stage1_event.py --observation_id <uuid>
  python scripts/prove_stage1_event.py --decision_id <uuid>
  python scripts/prove_stage1_event.py --lead_id <uuid>
  python scripts/prove_stage1_event.py --all
"""
import asyncio
import json
import os
import sys
import argparse
from datetime import datetime, timezone

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


async def prove_chain(conn, args):
    """Proves the complete evidence chain for given identifiers."""
    sep = "-" * 70
    
    print(sep)
    print("WEFYLABS STAGE-1 EVIDENCE FORENSIC PROVER")
    print("Timestamp: " + datetime.now(timezone.utc).isoformat())
    print(sep)

    # Collect target observations
    target_obs_ids = set()

    if args.observation_id:
        target_obs_ids.add(args.observation_id)

    if args.decision_id:
        row = await conn.fetchrow(
            "SELECT observation_id FROM pilot_human_decisions WHERE id = $1",
            args.decision_id
        )
        if row and row["observation_id"]:
            target_obs_ids.add(str(row["observation_id"]))
            print("Decision " + args.decision_id + " -> observation " + str(row["observation_id"]))
        else:
            print("ERROR: Decision " + args.decision_id + " not found or has no linked observation.")

    if args.lead_id:
        rows = await conn.fetch(
            "SELECT id FROM pilot_observations WHERE lead_id = $1",
            args.lead_id
        )
        for row in rows:
            target_obs_ids.add(str(row["id"]))
        print("Lead " + args.lead_id + " -> " + str(len(rows)) + " observation(s)")

    if args.all:
        rows = await conn.fetch("SELECT id FROM pilot_observations ORDER BY observed_at")
        for row in rows:
            target_obs_ids.add(str(row["id"]))
        print("All observations: " + str(len(target_obs_ids)) + " total")

    if not target_obs_ids:
        print("No target identifiers provided. Use --all to print all evidence.")
        return

    chains = []
    for obs_id in sorted(target_obs_ids):
        print("\n" + "=" * 50)
        print("EVIDENCE CHAIN FOR OBSERVATION: " + obs_id)
        print("=" * 50)

        chain = {"observation_id": obs_id, "valid": True, "issues": []}

        # 1. Observation
        obs = await conn.fetchrow(
            """
            SELECT o.id, o.pilot_id, o.organization_id, o.lead_id, o.agent_id,
                   o.recommended_action, o.agent_confidence, o.execution_mode,
                   o.pilot_stage, o.is_eligible_for_shadow_accuracy, o.is_synthetic,
                   o.observed_at, o.source_event_id, o.source_event_type,
                   o.policy_decision, o.policy_version
            FROM pilot_observations o
            WHERE o.id = $1
            """,
            obs_id
        )
        if not obs:
            print("ERROR: Observation not found in pilot_observations")
            chain["valid"] = False
            chain["issues"].append("Observation not found")
            chains.append(chain)
            continue

        org_id = str(obs["organization_id"])
        lead_id = str(obs["lead_id"]) if obs["lead_id"] else None
        print("\n[1] OBSERVATION")
        print("  id:               " + str(obs["id"]))
        print("  organization_id:  " + org_id)
        print("  lead_id:          " + str(lead_id))
        print("  agent_id:         " + str(obs["agent_id"]))
        print("  recommended:      " + str(obs["recommended_action"]))
        print("  confidence:       " + str(obs["agent_confidence"]))
        print("  execution_mode:   " + str(obs["execution_mode"]))
        print("  pilot_stage:      " + str(obs["pilot_stage"]))
        print("  is_synthetic:     " + str(obs["is_synthetic"]))
        print("  is_eligible:      " + str(obs["is_eligible_for_shadow_accuracy"]))
        print("  observed_at:      " + (obs["observed_at"].isoformat() if obs["observed_at"] else "None"))
        print("  source_event_id:  " + str(obs["source_event_id"]))
        print("  policy_decision:  " + str(obs["policy_decision"]))

        if obs["is_synthetic"]:
            chain["issues"].append("SYNTHETIC OBSERVATION: is_synthetic = TRUE")
            chain["valid"] = False
            print("  *** WARNING: SYNTHETIC OBSERVATION ***")

        chain["observation"] = {
            "id": obs_id,
            "org_id": org_id,
            "lead_id": lead_id,
            "agent_id": obs["agent_id"],
            "recommended_action": obs["recommended_action"],
            "is_synthetic": bool(obs["is_synthetic"]),
            "observed_at": obs["observed_at"].isoformat() if obs["observed_at"] else None,
        }

        # 2. Lead
        if lead_id:
            try:
                lead = await conn.fetchrow(
                    "SELECT id, organization_id, name FROM leads WHERE id = $1",
                    lead_id
                )
                if lead:
                    lead_org = str(lead["organization_id"])
                    print("\n[2] LEAD")
                    print("  id:              " + str(lead["id"]))
                    print("  name:            " + str(lead["name"]) if lead["name"] else "  name: NULL")
                    print("  organization_id: " + lead_org)
                    if lead_org != org_id:
                        chain["issues"].append("TENANT VIOLATION: Lead org " + lead_org + " != observation org " + org_id)
                        chain["valid"] = False
                        print("  *** CROSS-TENANT VIOLATION ***")
                    else:
                        print("  tenant: ISOLATED (same org)")
                    chain["lead"] = {"id": lead_id, "org_id": lead_org}
                else:
                    print("\n[2] LEAD: NOT FOUND in leads table (may be from different schema or deleted)")
                    chain["issues"].append("Lead " + lead_id + " not found in leads table")
            except Exception as e:
                print("\n[2] LEAD: ERROR - " + str(e))

        # 3. Human Decision
        decisions = await conn.fetch(
            """
            SELECT id, organization_id, lead_id, human_actor_id, human_actor_role,
                   decision_type, action_taken, reason, decided_at
            FROM pilot_human_decisions
            WHERE observation_id = $1
            ORDER BY decided_at
            """,
            obs_id
        )
        print("\n[3] HUMAN DECISIONS (" + str(len(decisions)) + " for this observation)")
        chain["human_decisions"] = []
        for d in decisions:
            dec_org = str(d["organization_id"])
            print("  Decision ID: " + str(d["id"]))
            print("    org_id:      " + dec_org)
            print("    actor_id:    " + str(d["human_actor_id"]))
            print("    actor_role:  " + str(d["human_actor_role"]))
            print("    type:        " + str(d["decision_type"]))
            print("    action:      " + str(d["action_taken"]))
            print("    decided_at:  " + (d["decided_at"].isoformat() if d["decided_at"] else "None"))
            if dec_org != org_id:
                chain["issues"].append("TENANT VIOLATION: Decision org " + dec_org + " != observation org " + org_id)
                chain["valid"] = False
            chain["human_decisions"].append({
                "id": str(d["id"]),
                "org_id": dec_org,
                "decision_type": d["decision_type"],
                "action_taken": d["action_taken"],
                "decided_at": d["decided_at"].isoformat() if d["decided_at"] else None,
            })

        if len(decisions) == 0:
            print("  (no decisions yet — observation pending human review)")

        # 4. Audit events
        pilot_row = await conn.fetchrow(
            "SELECT id FROM pilot_tenants WHERE organization_id = $1", org_id
        )
        if pilot_row:
            audit_events = await conn.fetch(
                """
                SELECT sequence_number, event_type, current_hash, previous_hash, created_at
                FROM pilot_audit_events
                WHERE pilot_id = $1
                ORDER BY sequence_number
                """,
                str(pilot_row["id"])
            )
            print("\n[4] AUDIT CHAIN (" + str(len(audit_events)) + " events for this pilot)")
            prev = None
            chain_ok = True
            for a in audit_events:
                status = "OK"
                if prev is not None and a["previous_hash"] != prev:
                    status = "CHAIN_BREAK"
                    chain_ok = False
                    chain["issues"].append("Audit chain break at seq " + str(a["sequence_number"]))
                print("  Seq " + str(a["sequence_number"]) + ": " + a["event_type"] +
                      " | " + str(a["current_hash"])[:16] + "... [" + status + "]")
                prev = a["current_hash"]
            chain["audit_chain_valid"] = chain_ok
            print("  Chain: " + ("VALID" if chain_ok else "BROKEN"))
        else:
            print("\n[4] AUDIT: No pilot found for org " + org_id)

        # 5. Provider side effects
        try:
            action_records = await conn.fetch(
                """
                SELECT id, action_type, semantic_state, execution_mode, created_at
                FROM pilot_action_records
                WHERE organization_id = $1
                ORDER BY created_at
                LIMIT 20
                """,
                org_id
            )
            non_shadow = [a for a in action_records if a["execution_mode"] != "SHADOW"]
            print("\n[5] PROVIDER SIDE EFFECTS")
            print("  Total action records for org: " + str(len(action_records)))
            print("  Non-shadow dispatches:        " + str(len(non_shadow)))
            if non_shadow:
                chain["issues"].append("Non-shadow provider dispatches found: " + str(len(non_shadow)))
                chain["valid"] = False
                for a in non_shadow:
                    print("  *** NON-SHADOW DISPATCH: " + str(a["action_type"]) + " state=" + str(a["semantic_state"]) + " ***")
            chain["provider_dispatches"] = len(non_shadow)
        except Exception as e:
            print("\n[5] ACTION RECORDS: ERROR - " + str(e))

        # Chain summary
        print("\n[CHAIN VERDICT]")
        if chain["valid"] and not chain["issues"]:
            print("  STATUS: VALID EVIDENCE CHAIN")
        else:
            print("  STATUS: ISSUES DETECTED")
            for issue in chain["issues"]:
                print("  ISSUE: " + issue)

        chains.append(chain)

    # Overall summary
    print("\n" + sep)
    print("FORENSIC SUMMARY")
    print(sep)
    all_valid = all(c["valid"] for c in chains)
    print("Chains analyzed:   " + str(len(chains)))
    print("All chains valid:  " + str(all_valid))
    for c in chains:
        status = "VALID" if c["valid"] else "INVALID"
        print("  " + c["observation_id"][:8] + "... -> " + status)
        for issue in c.get("issues", []):
            print("    ISSUE: " + issue)

    return chains


async def main():
    parser = argparse.ArgumentParser(description="Prove Stage-1 evidence chain from live DB")
    parser.add_argument("--observation_id", type=str, default=None)
    parser.add_argument("--decision_id", type=str, default=None)
    parser.add_argument("--lead_id", type=str, default=None)
    parser.add_argument("--all", action="store_true", default=False)
    args = parser.parse_args()

    if not any([args.observation_id, args.decision_id, args.lead_id, args.all]):
        # Default: prove all known observations
        args.all = True

    import asyncpg
    pg_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_url, timeout=30)
    try:
        await prove_chain(conn, args)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
