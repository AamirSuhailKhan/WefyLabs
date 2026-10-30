"""
Phase 5 E2E Pilot Acceptance & Failure Recovery Test Script (Remediated - Master Prompt 6)
==========================================================================================
Executes complete CRM dry run for Phase C, Phase D, and Phase E with FAIL-CLOSED isolation:
1. Validates test database target via `validate_test_database_target`.
   STRICTLY REFUSES TO EXECUTE AGAINST 'leadscore' OR PRODUCTION DATABASES.
2. Tracks synthetic entities via `TestEntityTracker`.
3. Executes:
   - Synthetic Tenant Onboarding
   - Full CRM Lead Lifecycle (Create, Validate, Status, Stage, Notes, Tasks)
   - Multi-Tenant IDOR Rejection
   - Failure & Recovery Edge Cases (Expired Auth, Malformed Input, 404s, Rollback)
4. Bounded safe cleanup of registered test-owned primary keys only.
"""
import os
import sys
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Ensure apps/api is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
API_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "apps", "api"))
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

from app.config import settings
from app.core.database_safety import (
    validate_test_database_target,
    is_live_or_shared_database,
    UnsafeDatabaseTargetError,
    TestEntityTracker,
)
from app.main import app
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.organization import Organization, OrganizationMember
from app.models.crm_models import Task, LeadNote
from app.modules.auth.service import create_access_token


async def run_dry_run(target_db_url: str = None):
    # ─── FAIL-CLOSED SAFETY LOCK ──────────────────────────────────────────
    db_url = target_db_url or settings.DATABASE_URL
    current_env = getattr(settings, "ENV", "testing")

    print(f"[0/6] Validating database target safety...")
    print(f"      Environment: {current_env}")
    try:
        db_name = validate_test_database_target(db_url, env=current_env)
        print(f"      Target validated: '{db_name}' (Isolated Test Database)")
    except Exception as exc:
        print(f"\nFATAL DATABASE SAFETY INTERCEPT: {exc}")
        print("Execution aborted to protect application database integrity.")
        raise

    # Create isolated test engine
    test_engine = create_async_engine(db_url, echo=False)
    SessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    tracker = TestEntityTracker(test_run_id=f"acceptance-{uuid.uuid4().hex[:8]}")

    print("\n[1/6] Initializing Synthetic Test Organization and Brokers...")
    results = {}

    org_id = uuid.uuid4()
    org_slug = f"pilot-synthetic-{uuid.uuid4().hex[:8]}"
    competitor_org_id = uuid.uuid4()
    competitor_slug = f"competitor-{uuid.uuid4().hex[:8]}"

    owner_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    competitor_broker_id = uuid.uuid4()

    owner_email = f"owner_{uuid.uuid4().hex[:6]}@pilot.wefylabs.test"
    agent_email = f"agent_{uuid.uuid4().hex[:6]}@pilot.wefylabs.test"
    competitor_email = f"competitor_{uuid.uuid4().hex[:6]}@wefylabs.test"

    async with SessionLocal() as session:
        # Create Organizations
        pilot_org = Organization(
            id=org_id,
            name="Pilot Synthetic Realty",
            slug=org_slug,
            plan="enterprise",
            country_code="IN",
            currency_code="INR",
            business_type="brokerage",
            team_size="6-20",
            is_demo=True
        )
        comp_org = Organization(
            id=competitor_org_id,
            name="Competitor Real Estate",
            slug=competitor_slug,
            plan="starter",
            country_code="IN",
            currency_code="INR",
            is_demo=True
        )
        session.add_all([pilot_org, comp_org])
        tracker.register("organizations", org_id)
        tracker.register("organizations", competitor_org_id)

        # Create Brokers
        b_owner = Broker(
            id=owner_id,
            email=owner_email,
            name="Pilot Owner",
            phone=f"+9198{uuid.uuid4().int % 100000000:08d}",
            whatsapp_number=f"+9198{uuid.uuid4().int % 100000000:08d}",
            subscription_status="active"
        )
        b_agent = Broker(
            id=agent_id,
            email=agent_email,
            name="Pilot Agent",
            phone=f"+9197{uuid.uuid4().int % 100000000:08d}",
            whatsapp_number=f"+9197{uuid.uuid4().int % 100000000:08d}",
            subscription_status="active"
        )
        b_competitor = Broker(
            id=competitor_broker_id,
            email=competitor_email,
            name="Competitor Agent",
            phone=f"+9196{uuid.uuid4().int % 100000000:08d}",
            whatsapp_number=f"+9196{uuid.uuid4().int % 100000000:08d}",
            subscription_status="active"
        )
        session.add_all([b_owner, b_agent, b_competitor])
        tracker.register("brokers", owner_id)
        tracker.register("brokers", agent_id)
        tracker.register("brokers", competitor_broker_id)
        await session.flush()

        # Memberships
        m_owner = OrganizationMember(organization_id=org_id, broker_id=owner_id, role="owner")
        m_agent = OrganizationMember(organization_id=org_id, broker_id=agent_id, role="agent")
        m_comp = OrganizationMember(organization_id=competitor_org_id, broker_id=competitor_broker_id, role="owner")
        session.add_all([m_owner, m_agent, m_comp])
        tracker.register_membership(org_id, owner_id)
        tracker.register_membership(org_id, agent_id)
        tracker.register_membership(competitor_org_id, competitor_broker_id)

        await session.commit()
    print("   -> Synthetic organizations and brokers provisioned in isolated database.")

    # Tokens
    owner_token = create_access_token({"sub": owner_email, "email": owner_email})
    agent_token = create_access_token({"sub": agent_email, "email": agent_email})
    comp_token = create_access_token({"sub": competitor_email, "email": competitor_email})

    owner_headers = {
        "Authorization": f"Bearer {owner_token}",
        "X-WefyLabs-Organization-Id": str(org_id)
    }
    agent_headers = {
        "Authorization": f"Bearer {agent_token}",
        "X-WefyLabs-Organization-Id": str(org_id)
    }
    comp_headers = {
        "Authorization": f"Bearer {comp_token}",
        "X-WefyLabs-Organization-Id": str(competitor_org_id)
    }

    created_lead_id = None
    created_task_id = None

    # Patch dependency session for FastAPI application
    from app.database import get_db
    async def get_test_db():
        async with SessionLocal() as s:
            yield s

    app.dependency_overrides[get_db] = get_test_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000") as ac:
            print("[2/6] Phase C: Tenant Onboarding & Boundary Checks...")
            # C.1 Unauthenticated rejected
            res_unauth = await ac.get("/api/v1/leads")
            assert res_unauth.status_code in (401, 403), f"Unauth failed: {res_unauth.status_code}"
            results["C1_unauth_rejected"] = True

            # C.2 Header spoofing rejection
            spoofed_headers = {
                "Authorization": f"Bearer {comp_token}",
                "X-WefyLabs-Organization-Id": str(org_id)
            }
            res_spoof = await ac.get("/api/v1/leads", headers=spoofed_headers)
            assert res_spoof.status_code == 403, f"Header spoofing not rejected: {res_spoof.status_code}"
            results["C2_header_spoofing_rejected"] = True

            print("[3/6] Phase D: Executing CRM Lead Lifecycle Scenario...")
            # D.1 Invalid Lead Payload
            res_invalid = await ac.post("/api/v1/leads", json={"name": ""}, headers=owner_headers)
            assert res_invalid.status_code == 422, f"Validation failed to reject invalid lead: {res_invalid.status_code}"
            results["D1_lead_validation_422"] = True

            # D.2 Create Synthetic Lead
            lead_payload = {
                "name": "Shri Rajesh Kumar",
                "phone": "+919812345678",
                "email": "rajesh.kumar@example.test",
                "source": "website",
                "budget_min": 15000000,
                "budget_max": 25000000,
                "preferred_locations": ["Indiranagar", "Koramangala"],
                "property_type": "3BHK",
                "notes": "Looking for ready-to-move apartment near tech park."
            }
            res_create = await ac.post("/api/v1/leads", json=lead_payload, headers=owner_headers)
            assert res_create.status_code == 201, f"Lead creation failed: {res_create.status_code} - {res_create.text}"
            lead_data = res_create.json()
            created_lead_id = lead_data["id"]
            tracker.register("leads", created_lead_id)
            assert lead_data["name"] == "Shri Rajesh Kumar"
            
            # Verify in isolated database
            async with SessionLocal() as session:
                lead_in_db = await session.get(Lead, uuid.UUID(created_lead_id))
                assert lead_in_db is not None
                assert str(lead_in_db.organization_id) == str(org_id)
            results["D2_lead_created_201"] = True

            # D.3 Read Lead Detail
            res_detail = await ac.get(f"/api/v1/leads/{created_lead_id}", headers=owner_headers)
            assert res_detail.status_code == 200
            assert res_detail.json()["id"] == created_lead_id
            results["D3_lead_detail_read_200"] = True

            # D.4 Update Lead Status
            res_status = await ac.patch(
                f"/api/v1/leads/{created_lead_id}/status",
                json={"status": "active"},
                headers=owner_headers
            )
            assert res_status.status_code == 200
            assert res_status.json()["status"] == "active"
            results["D4_lead_status_updated"] = True

            # D.5 Update Lead Stage
            res_stage = await ac.patch(
                f"/api/v1/leads/{created_lead_id}/stage",
                json={"stage": "contacted"},
                headers=owner_headers
            )
            assert res_stage.status_code == 200
            assert res_stage.json()["pipeline_stage"] == "contacted"
            results["D5_lead_stage_updated"] = True

            # D.6 Record Interaction Note
            note_payload = {
                "content": "Client confirmed interest in 3BHK high-rise. Scheduled site visit for Saturday 11am.",
                "note_type": "call_log"
            }
            res_note = await ac.post(
                f"/api/v1/leads/{created_lead_id}/notes",
                json=note_payload,
                headers=owner_headers
            )
            assert res_note.status_code == 200
            results["D6_lead_note_recorded"] = True

            # D.7 Create Follow-Up Task
            task_payload = {
                "title": "Conduct Indiranagar site visit with Rajesh Kumar",
                "lead_id": created_lead_id,
                "description": "Show unit 402 and 501. Bring property brochures.",
                "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
                "priority": "high"
            }
            res_task = await ac.post("/api/v1/tasks", json=task_payload, headers=owner_headers)
            assert res_task.status_code == 201, f"Task creation failed: {res_task.status_code} - {res_task.text}"
            task_data = res_task.json()
            created_task_id = task_data["id"]
            tracker.register("tasks", created_task_id)
            assert task_data["title"] == task_payload["title"]
            results["D7_followup_task_created"] = True

            # D.8 List Tasks
            res_tasks_list = await ac.get("/api/v1/tasks", headers=owner_headers)
            assert res_tasks_list.status_code == 200
            task_ids = [t["id"] for t in res_tasks_list.json()]
            assert created_task_id in task_ids
            results["D8_tasks_listed_in_org"] = True

            # D.9 Cross-Tenant Isolation
            res_idor = await ac.get(f"/api/v1/leads/{created_lead_id}", headers=comp_headers)
            assert res_idor.status_code == 404, f"IDOR vulnerability detected! Code: {res_idor.status_code}"
            results["D9_cross_tenant_idor_rejected_404"] = True

            # D.10 Outbound Inert Gating
            is_dispatch_enabled = getattr(settings, "FOLLOWUP_HUB_DISPATCH_ENABLED", False)
            assert is_dispatch_enabled is False
            results["D10_outbound_dispatch_inert"] = True

            print("[4/6] Phase E: Testing Failure & Recovery Edge Cases...")
            # E.1 Expired Token
            expired_token = create_access_token(
                {"sub": owner_email, "email": owner_email},
                expires_delta=timedelta(seconds=-60)
            )
            res_expired = await ac.get(
                "/api/v1/leads",
                headers={"Authorization": f"Bearer {expired_token}"}
            )
            assert res_expired.status_code == 401, f"Expired token not rejected: {res_expired.status_code}"
            results["E1_expired_token_rejected_401"] = True

            # E.2 Malformed UUID
            res_malformed = await ac.get("/api/v1/leads/not-a-valid-uuid", headers=owner_headers)
            assert res_malformed.status_code == 422, f"Malformed UUID not rejected: {res_malformed.status_code}"
            results["E2_malformed_uuid_422"] = True

            # E.3 Non-existent Lead ID
            random_id = uuid.uuid4()
            res_nonexistent = await ac.get(f"/api/v1/leads/{random_id}", headers=owner_headers)
            assert res_nonexistent.status_code == 404
            results["E3_nonexistent_lead_404"] = True

            # E.4 Database Transaction Rollback Safety
            async with SessionLocal() as session:
                try:
                    async with session.begin():
                        session.add(Broker(id=owner_id, email=owner_email))
                        await session.flush()
                except Exception:
                    await session.rollback()
                    check_res = await session.execute(select(Lead).where(Lead.id == created_lead_id))
                    lead_chk = check_res.scalars().first()
                    assert lead_chk is not None
                    results["E4_tx_rollback_safety"] = True

    finally:
        # Revert dependency override
        app.dependency_overrides.pop(get_db, None)

        print("[5/6] Cleaning up Test-Owned Synthetic Entities via TestEntityTracker...")
        async with SessionLocal() as session:
            cleanup_summary = await tracker.safe_cleanup(session)
            print(f"      Purge Ledger: {cleanup_summary['records_purged']}")
        await test_engine.dispose()

    print("\n[6/6] Final Remediated Acceptance Summary:")
    all_passed = True
    for test_name, status in results.items():
        print(f"  - {test_name}: {'PASS' if status else 'FAIL'}")
        if not status:
            all_passed = False

    assert all_passed, "One or more acceptance steps failed!"
    print("\n>>> ALL REMEDIATED ACCEPTANCE TESTS PASSED ON ISOLATED TEST DATA <<<")


if __name__ == "__main__":
    # If executed without args, target isolated test database
    isolated_db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore_test_acceptance"
    )
    asyncio.run(run_dry_run(target_db_url=isolated_db_url))
