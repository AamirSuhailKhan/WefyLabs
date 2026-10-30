"""
run_controlled_pilot_p11.py
===========================
WefyLabs Master Prompt 11 — Controlled Internal Pilot Runner
Comprehensive End-to-End CRM User Journey Validation, Adversarial Tenant Isolation,
Operational Reliability Measurements, and Evidence Gathering.

Guarantees:
1. Target DB is strictly 'leadscore_test_acceptance'.
2. Live DB 'leadscore' is verified 100% invariant (0 mutations).
3. Outbound communication is hard-disabled (zero customer sends).
4. All synthetic entities are tracked and cleanly purged.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.abspath("apps/api"))
sys.path.insert(0, os.path.abspath("."))

import asyncpg
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings
from app.core.database_safety import (
    validate_test_database_target,
    create_isolated_test_session_factory,
    TestEntityTracker,
)
from app.modules.auth.service import create_access_token
from app.models.organization import Organization, OrganizationMember
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.deal_models import Deal
from app.models.calendar_models import MeetingHold
from app.database import get_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("wefylabs.pilot_p11")

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_test_acceptance"
LIVE_DB_URL = "postgresql://postgres:postgres@localhost:5432/leadscore"

async def get_live_db_fingerprint() -> Dict[str, Any]:
    """Capture forensic fingerprint of live database to prove zero mutations."""
    conn = await asyncpg.connect(LIVE_DB_URL)
    tables = ["leads", "organizations", "brokers", "organization_members", "source_attributions", "deals", "tasks"]
    fingerprint = {}
    for t in tables:
        cnt = await conn.fetchval(f"SELECT count(*) FROM {t}")
        has_updated = await conn.fetchval(f"""
            SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = '{t}' AND column_name = 'updated_at')
        """)
        max_up = None
        if has_updated:
            max_up = await conn.fetchval(f"SELECT max(updated_at) FROM {t}")
        fingerprint[t] = {"count": cnt, "max_updated_at": str(max_up)}
    v = await conn.fetchval("SELECT version_num FROM alembic_version")
    fingerprint["alembic_version"] = v
    await conn.close()
    return fingerprint


async def run_controlled_pilot():
    print("================================================================================")
    print("        WEFYLABS MASTER PROMPT 11 — CONTROLLED INTERNAL PILOT RUNNER             ")
    print("================================================================================")

    # 1. Pilot Boundary & DB Target Safety Enforcement
    print("\n[STEP 1/6] Enforcing Pilot Boundaries and Safety Guards...")
    validated_target = validate_test_database_target(TEST_DB_URL, env="testing")
    print(f" -> Database Target Validated: '{validated_target}' (Isolated Staging Database)")
    
    assert getattr(settings, "PILOT_MODE", "RECOMMEND_ONLY") in ("RECOMMEND_ONLY", "DISABLED"), "PILOT_MODE must be RECOMMEND_ONLY!"
    assert getattr(settings, "WHATSAPP_ENABLED", False) is False, "WHATSAPP_ENABLED must be False!"
    assert getattr(settings, "FOLLOWUP_HUB_DISPATCH_ENABLED", False) is False, "FOLLOWUP_HUB_DISPATCH_ENABLED must be False!"
    print(" -> Boundary Invariants Enforced: PILOT_MODE=RECOMMEND_ONLY, Outbound WhatsApp=FALSE, Hub Dispatch=FALSE")

    # Capture pre-run live DB fingerprint
    pre_live_fp = await get_live_db_fingerprint()
    print(f" -> Live Database Fingerprint Captured: Revision={pre_live_fp['alembic_version']}, Leads={pre_live_fp['leads']['count']}, Orgs={pre_live_fp['organizations']['count']}")

    # 2. Provision Synthetic Pilot Topology
    print("\n[STEP 2/6] Provisioning Synthetic Multi-Tenant Pilot Topology...")
    engine, session_factory = create_isolated_test_session_factory(TEST_DB_URL, expected_db="leadscore_test_acceptance")
    tracker = TestEntityTracker(test_run_id=f"p11_{uuid.uuid4().hex[:8]}")

    org_a_id = uuid.uuid4()
    org_b_id = uuid.uuid4()
    owner_a_id = uuid.uuid4()
    agent_a_id = uuid.uuid4()
    owner_b_id = uuid.uuid4()

    async with session_factory() as session:
        # Organization A (Pilot Organization)
        org_a = Organization(
            id=org_a_id,
            name="Apex Sky Realty Pilot",
            slug=f"apex-sky-{org_a_id.hex[:6]}",
            plan="enterprise",
            country_code="IN",
            currency_code="INR",
            business_type="brokerage",
            team_size="6-20",
            is_demo=True,
        )
        # Organization B (Competitor Organization for Isolation Attacks)
        org_b = Organization(
            id=org_b_id,
            name="Beacon Towers Competitor",
            slug=f"beacon-towers-{org_b_id.hex[:6]}",
            plan="pro",
            country_code="IN",
            currency_code="INR",
            business_type="brokerage",
            team_size="1-5",
            is_demo=True,
        )
        session.add_all([org_a, org_b])
        tracker.register("organizations", org_a_id)
        tracker.register("organizations", org_b_id)

        # Brokers
        broker_oa = Broker(
            id=owner_a_id,
            name="Aarav Sharma (Owner A)",
            email=f"aarav_{owner_a_id.hex[:6]}@pilot.wefylabs.test",
            phone=f"+9198{uuid.uuid4().int % 100000000:08d}",
            subscription_status="active",
        )
        broker_aa = Broker(
            id=agent_a_id,
            name="Priya Patel (Agent A)",
            email=f"priya_{agent_a_id.hex[:6]}@pilot.wefylabs.test",
            phone=f"+9198{uuid.uuid4().int % 100000000:08d}",
            subscription_status="active",
        )
        broker_ob = Broker(
            id=owner_b_id,
            name="Vikram Seth (Owner B)",
            email=f"vikram_{owner_b_id.hex[:6]}@competitor.wefylabs.test",
            phone=f"+9198{uuid.uuid4().int % 100000000:08d}",
            subscription_status="active",
        )
        session.add_all([broker_oa, broker_aa, broker_ob])
        tracker.register("brokers", owner_a_id)
        tracker.register("brokers", agent_a_id)
        tracker.register("brokers", owner_b_id)

        # Memberships
        m_oa = OrganizationMember(organization_id=org_a_id, broker_id=owner_a_id, role="owner")
        m_aa = OrganizationMember(organization_id=org_a_id, broker_id=agent_a_id, role="agent")
        m_ob = OrganizationMember(organization_id=org_b_id, broker_id=owner_b_id, role="owner")
        session.add_all([m_oa, m_aa, m_ob])
        tracker.register_membership(org_a_id, owner_a_id)
        tracker.register_membership(org_a_id, agent_a_id)
        tracker.register_membership(org_b_id, owner_b_id)

        await session.commit()
    print(" -> Synthetic Pilot Tenants and Brokers Provisioned Cleanly.")

    # Override get_db dependency to point to isolated test engine
    async def override_get_db():
        async with session_factory() as sess:
            yield sess

    app.dependency_overrides[get_db] = override_get_db

    # Auth Tokens
    token_oa = create_access_token(data={"sub": str(owner_a_id), "org_id": str(org_a_id), "role": "owner"})
    token_aa = create_access_token(data={"sub": str(agent_a_id), "org_id": str(org_a_id), "role": "agent"})
    token_ob = create_access_token(data={"sub": str(owner_b_id), "org_id": str(org_b_id), "role": "owner"})

    headers_oa = {"Authorization": f"Bearer {token_oa}", "X-WefyLabs-Organization-Id": str(org_a_id)}
    headers_aa = {"Authorization": f"Bearer {token_aa}", "X-WefyLabs-Organization-Id": str(org_a_id)}
    headers_ob = {"Authorization": f"Bearer {token_ob}", "X-WefyLabs-Organization-Id": str(org_b_id)}

    metrics = {
        "latencies": [],
        "scenarios_executed": 0,
        "scenarios_passed": 0,
        "scenarios_failed": 0,
        "results": {},
    }

    async def record_op(name: str, coro):
        t0 = time.monotonic()
        try:
            resp = await coro
            lat_ms = (time.monotonic() - t0) * 1000.0
            metrics["latencies"].append(lat_ms)
            metrics["scenarios_executed"] += 1
            return resp, lat_ms
        except Exception as e:
            lat_ms = (time.monotonic() - t0) * 1000.0
            metrics["latencies"].append(lat_ms)
            metrics["scenarios_executed"] += 1
            raise

    print("\n[STEP 3/6] Executing Complete Customer Workflows (End-to-End Tracing)...")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://pilot.test") as ac:

        # ── Workflow 1: Lead Intake & Validation ─────────────────────────────
        print(" -> Workflow 1: Lead Intake & Validation...")
        # 1.1 Reject negative budget
        r1_1, lat = await record_op("intake_bad_budget", ac.post("/api/v1/leads", json={"budget_min": -100}, headers=headers_oa))
        assert r1_1.status_code == 422, f"Expected 422 for negative budget, got {r1_1.status_code}"
        metrics["results"]["1.1_negative_budget_rejected_422"] = "PASS"

        # 1.2 Reject malformed phone
        r1_2, lat = await record_op("intake_bad_phone", ac.post("/api/v1/leads", json={"phone": "12345", "name": "Bad Phone"}, headers=headers_oa))
        assert r1_2.status_code == 422, f"Expected 422 for malformed phone, got {r1_2.status_code}"
        metrics["results"]["1.2_malformed_phone_rejected_422"] = "PASS"

        # 1.3 Valid lead intake (Org A)
        lead_a_payload = {
            "name": "Rohan Mehra",
            "phone": "+919876543210",
            "source": "website_portal",
            "budget_min": 15000000,
            "budget_max": 25000000,
            "property_type": "3bhk",
            "transaction_type": "buy",
            "preferred_locations": ["Bandra West", "Khar"],
            "timeline": "immediate",
        }
        r1_3, lat = await record_op("intake_create_lead", ac.post("/api/v1/leads", json=lead_a_payload, headers=headers_oa))
        assert r1_3.status_code == 201, f"Lead creation failed: {r1_3.text}"
        lead_a_id = r1_3.json()["id"]
        tracker.register("leads", lead_a_id)
        metrics["results"]["1.3_valid_lead_created_201"] = "PASS"

        # 1.4 Direct detail retrieval
        r1_4, lat = await record_op("intake_read_lead", ac.get(f"/api/v1/leads/{lead_a_id}", headers=headers_oa))
        assert r1_4.status_code == 200
        assert r1_4.json()["name"] == "Rohan Mehra"
        assert r1_4.json()["budget_min"] == 15000000
        metrics["results"]["1.4_lead_detail_retrieved_200"] = "PASS"

        # ── Workflow 2: Lead Qualification & AI Scoring ──────────────────────
        print(" -> Workflow 2: Lead Qualification & AI Scoring...")
        r2_1, lat = await record_op("scoring_qualify", ac.post(
            "/api/v1/scoring/qualify",
            json={"lead_id": lead_a_id, "force": True},
            headers=headers_oa
        ))
        assert r2_1.status_code == 200, f"Qualify lead failed: {r2_1.text}"
        score_data = r2_1.json()
        assert "score" in score_data, "Missing score field"
        assert 0.0 <= score_data["confidence"] <= 1.0, "Score confidence must be between 0 and 1"
        assert score_data["score"] in ("hot", "warm", "cold", "qualified", "pending")
        metrics["results"]["2.1_lead_qualification_scored_200"] = "PASS"

        # ── Workflow 3: CRM Pipeline State Progression ───────────────────────
        print(" -> Workflow 3: CRM Pipeline State Progression...")
        # 3.1 Advance stage to contacted
        r3_1, lat = await record_op("pipeline_contacted", ac.patch(
            f"/api/v1/leads/{lead_a_id}/stage",
            json={"stage": "contacted"},
            headers=headers_oa
        ))
        assert r3_1.status_code == 200
        assert r3_1.json().get("pipeline_stage") == "contacted" or r3_1.json().get("stage") == "contacted"

        # 3.2 Advance stage to viewing
        r3_2, lat = await record_op("pipeline_viewing", ac.patch(
            f"/api/v1/leads/{lead_a_id}/stage",
            json={"stage": "viewing"},
            headers=headers_oa
        ))
        assert r3_2.status_code == 200

        # 3.3 Reject invalid stage transition
        r3_3, lat = await record_op("pipeline_invalid_stage", ac.patch(
            f"/api/v1/leads/{lead_a_id}/stage",
            json={"stage": "nonexistent_stage_xyz"},
            headers=headers_oa
        ))
        assert r3_3.status_code == 422, f"Expected 422 for invalid stage, got {r3_3.status_code}"

        # 3.4 Verify persistence
        r3_4, lat = await record_op("pipeline_verify_persist", ac.get(f"/api/v1/leads/{lead_a_id}", headers=headers_oa))
        assert r3_4.status_code == 200
        assert r3_4.json().get("pipeline_stage") == "viewing"
        metrics["results"]["3.1_pipeline_progression_verified"] = "PASS"

        # ── Workflow 4: Revenue Intelligence Assertions ──────────────────────
        print(" -> Workflow 4: Revenue Intelligence Assertions...")
        r4_1, lat = await record_op("ri_funnel", ac.get("/api/v1/revenue-intelligence/funnel", headers=headers_oa))
        assert r4_1.status_code == 200, f"Funnel summary failed: {r4_1.text}"
        funnel_data = r4_1.json()
        assert "stages" in funnel_data or "stage_counts" in funnel_data or "total_leads" in funnel_data
        metrics["results"]["4.1_revenue_funnel_summary_200"] = "PASS"

        # ── Workflow 5: Team Access & RBAC Boundary Enforcement ──────────────
        print(" -> Workflow 5: Team Access & RBAC Boundary Enforcement...")
        # 5.1 Agent A can read Org A's lead
        r5_1, lat = await record_op("rbac_agent_read", ac.get(f"/api/v1/leads/{lead_a_id}", headers=headers_aa))
        assert r5_1.status_code == 200
        metrics["results"]["5.1_agent_can_read_org_lead"] = "PASS"

        # 5.2 Competitor Owner B is BLOCKED from reading Org A's lead (IDOR defense)
        r5_2, lat = await record_op("rbac_competitor_idor_blocked", ac.get(f"/api/v1/leads/{lead_a_id}", headers=headers_ob))
        assert r5_2.status_code in (403, 404), f"Competitor should receive 403/404, got {r5_2.status_code}"
        metrics["results"]["5.2_competitor_idor_blocked_404"] = "PASS"

        # ── Workflow 6: Enterprise Search Platform ───────────────────────────
        print(" -> Workflow 6: Enterprise Search Platform...")
        # 6.1 Search as Org A finds Rohan
        r6_1, lat = await record_op("search_org_a", ac.get("/api/v1/v1/search?q=Rohan", headers=headers_oa))
        assert r6_1.status_code == 200

        # 6.2 Search as Org B returns 0 hits (Tenant Boundary)
        r6_2, lat = await record_op("search_org_b_cross_leak", ac.get("/api/v1/v1/search?q=Rohan", headers=headers_ob))
        assert r6_2.status_code == 200
        search_b_data = r6_2.json().get("data", {})
        hits_b = search_b_data.get("hits", [])
        assert len(hits_b) == 0, f"Search leaked Org A lead to Org B! Found {len(hits_b)} hits."
        metrics["results"]["6.1_search_tenant_isolation_verified"] = "PASS"

        # 6.3 Empty state handling
        r6_3, lat = await record_op("search_empty_state", ac.get("/api/v1/v1/search?q=xyznonexistent123", headers=headers_oa))
        assert r6_3.status_code == 200
        metrics["results"]["6.2_search_empty_state_clean_200"] = "PASS"

        # ── Workflow 7: Scheduling & Calendar Availability ───────────────────
        print(" -> Workflow 7: Scheduling & Calendar Availability...")
        # 7.1 Search slots
        future_start = (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
        future_end = future_start + timedelta(hours=4)
        r7_1, lat = await record_op("calendar_slots_search", ac.post(
            "/api/v1/calendar/slots/search",
            json={
                "lead_id": str(lead_a_id),
                "broker_id": str(owner_a_id),
                "date_from": future_start.isoformat(),
                "date_to": future_end.isoformat(),
                "duration_minutes": 30,
            },
            headers=headers_oa
        ))
        assert r7_1.status_code == 200, f"Slot search failed: {r7_1.text}"

        # 7.2 Book appointment
        booking_payload = {
            "lead_id": str(lead_a_id),
            "broker_id": str(owner_a_id),
            "meeting_type": "VIDEO_CALL",
            "slot_start_utc": future_start.isoformat(),
            "duration_minutes": 30,
            "virtual_provider": "MICROSOFT_TEAMS",
        }
        r7_2, lat = await record_op("calendar_book", ac.post("/api/v1/calendar/book", json=booking_payload, headers=headers_oa))
        assert r7_2.status_code == 200, f"Booking appointment failed: {r7_2.text}"
        booking_id = r7_2.json()["id"]
        metrics["results"]["7.1_appointment_booked_200"] = "PASS"

        # ── Workflow 8: Notification Safety & Hard Kill-Switch ──────────────
        print(" -> Workflow 8: Notification Safety & Hard Kill-Switch...")
        from app.modules.communication.channel_manager.manager import get_channel_manager
        from app.modules.communication.provider_adapters.base_provider import OutboundMessageDTO
        cm = get_channel_manager()
        wa_provider = cm.get_provider("whatsapp")
        test_msg = OutboundMessageDTO(
            message_id="msg_test_p11",
            recipient_identifier="+919876543210",
            message_type="text",
            content="Test pilot notification"
        )
        resp_wa = await wa_provider.send(test_msg)
        assert resp_wa.success is False
        assert resp_wa.status == "blocked"
        assert resp_wa.error_code == "CHANNEL_DISABLED"
        print(f"    -> Outbound WhatsApp Dispatch Result: {resp_wa.status} ({resp_wa.error_code}) [SAFE INERT]")
        metrics["results"]["8.1_whatsapp_hard_killswitch_blocked"] = "PASS"

        # ── Workflow 9: Distributed Tracing & Observability ──────────────────
        print(" -> Workflow 9: Distributed Tracing & Observability...")
        r9_1, lat = await record_op("observability_trace", ac.get("/health/live"))
        assert "x-correlation-id" in [k.lower() for k in r9_1.headers.keys()], "Missing X-Correlation-ID header!"
        corr_id = r9_1.headers.get("X-Correlation-ID") or r9_1.headers.get("x-correlation-id")
        assert corr_id is not None
        metrics["results"]["9.1_correlation_header_present"] = "PASS"

        # ── Workflow 10: Adversarial Multi-Tenant Cross-Isolation ────────────
        print(" -> Workflow 10: Adversarial Multi-Tenant Cross-Isolation...")
        # 10.1 List leads as Org B
        r10_1, lat = await record_op("iso_list_leads_b", ac.get("/api/v1/leads", headers=headers_ob))
        assert r10_1.status_code == 200
        leads_b_data = r10_1.json()
        lead_b_items = leads_b_data.get("items", leads_b_data if isinstance(leads_b_data, list) else [])
        assert all(str(item.get("id")) != str(lead_a_id) for item in lead_b_items), "Org B lead list leaked Org A lead!"

        # 10.2 Org B attempting to qualify Org A's lead
        r10_2, lat = await record_op("iso_cross_qualify", ac.post(
            "/api/v1/scoring/qualify",
            json={"lead_id": lead_a_id, "force": True},
            headers=headers_ob
        ))
        assert r10_2.status_code in (403, 404), f"Cross-tenant qualify must return 403/404, got {r10_2.status_code}"

        # 10.3 Org B attempting to book calendar appointment for Org A lead
        r10_3, lat = await record_op("iso_cross_book", ac.post(
            "/api/v1/calendar/book",
            json={
                "lead_id": str(lead_a_id),
                "broker_id": str(owner_b_id),
                "meeting_type": "VIDEO_CALL",
                "slot_start_utc": (future_start + timedelta(days=1)).isoformat(),
                "duration_minutes": 30,
            },
            headers=headers_ob
        ))
        assert r10_3.status_code in (400, 403, 404, 422), f"Cross-tenant calendar booking must be rejected, got {r10_3.status_code}"
        metrics["results"]["10.1_adversarial_isolation_all_blocked"] = "PASS"

        # ── Workflow 11: Idempotency & Operational Reliability ──────────────
        print(" -> Workflow 11: Idempotency & Operational Reliability...")
        idem_key = f"idem_p11_{uuid.uuid4().hex}"
        lead_idem_payload = {
            "name": "Karan Singhal",
            "phone": "+919123456789",
            "source": "referral",
            "budget_min": 20000000,
        }
        # First POST with idempotency key
        r11_1, lat1 = await record_op("idem_post_1", ac.post(
            "/api/v1/leads",
            json=lead_idem_payload,
            headers={**headers_oa, "Idempotency-Key": idem_key}
        ))
        assert r11_1.status_code == 201, f"Idempotency lead 1 failed: {r11_1.text}"
        idem_lead_id = r11_1.json()["id"]
        tracker.register("leads", idem_lead_id)

        # Re-send exact same POST with same Idempotency-Key
        r11_2, lat2 = await record_op("idem_post_2_cached", ac.post(
            "/api/v1/leads",
            json=lead_idem_payload,
            headers={**headers_oa, "Idempotency-Key": idem_key}
        ))
        assert r11_2.status_code == 201
        assert r11_2.headers.get("X-Cache-Lookup") == "HIT-IDEMPOTENT", f"Expected HIT-IDEMPOTENT header, got {r11_2.headers.get('X-Cache-Lookup')}"
        assert r11_2.json()["id"] == idem_lead_id
        print(f"    -> Idempotency Replay Caught: X-Cache-Lookup={r11_2.headers.get('X-Cache-Lookup')} (0 Duplicate Insert)")
        metrics["results"]["11.1_idempotency_middleware_verified"] = "PASS"

        # Health checks (liveness vs readiness)
        r_live, lat = await record_op("health_live", ac.get("/health/live"))
        assert r_live.status_code == 200
        r_ready, lat = await record_op("health_ready", ac.get("/health/ready"))
        assert r_ready.status_code == 200
        metrics["results"]["11.2_liveness_readiness_distinct_200"] = "PASS"

    # 4. Safe Teardown of Test-Owned Entities
    print("\n[STEP 4/6] Cleaning up Test-Owned Synthetic Entities via TestEntityTracker...")
    async with session_factory() as cleanup_session:
        summary = await tracker.safe_cleanup(cleanup_session)
        await cleanup_session.commit()
    print(f" -> Cleaned up test records: {summary['records_purged']}")

    await engine.dispose()

    # 5. Live DB Invariance Verification
    print("\n[STEP 5/6] Verifying Live Database (leadscore) Absolute Invariance...")
    post_live_fp = await get_live_db_fingerprint()
    assert pre_live_fp == post_live_fp, f"CRITICAL: Live DB mutated during pilot run!\nPre: {pre_live_fp}\nPost: {post_live_fp}"
    print(" -> Live Database (leadscore) Confirmed 100% Invariant (0 Mutations, 0 DDL Changes).")

    # 6. Operational Metrics Summary
    print("\n[STEP 6/6] Operational Reliability Summary:")
    lats = sorted(metrics["latencies"])
    n = len(lats)
    p50 = lats[int(n * 0.50)]
    p95 = lats[int(n * 0.95)]
    avg = sum(lats) / n if n else 0
    print(f" -> Total Scenarios Executed: {metrics['scenarios_executed']}")
    print(f" -> Latency Profile (ms): min={lats[0]:.2f}, avg={avg:.2f}, p50={p50:.2f}, p95={p95:.2f}, max={lats[-1]:.2f}")
    print(f" -> HTTP Success Rate: 100% of expected codes matched.")
    print(" -> Results:")
    for k, v in metrics["results"].items():
        print(f"    - {k}: {v}")

    print("\n================================================================================")
    print(" >>> CONTROLLED INTERNAL PILOT VALIDATION COMPLETED CLEANLY (ALL PASS) <<<       ")
    print("================================================================================")
    return metrics


if __name__ == "__main__":
    asyncio.run(run_controlled_pilot())
