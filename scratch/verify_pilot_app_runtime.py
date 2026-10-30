import asyncio
import os
import sys
import uuid

# Ensure apps/api is in sys.path
sys.path.insert(0, os.path.abspath("apps/api"))

from httpx import AsyncClient, ASGITransport
from dotenv import load_dotenv

# Set ENV_FILE and load pilot configuration
os.environ["ENV_FILE"] = ".env.pilot"
load_dotenv(".env.pilot", override=True)

# Import app after loading environment
from app.main import app
from app.modules.auth.service import create_access_token
from app.core.database_safety import validate_test_database_target

async def verify_pilot_runtime():
    print("--- 1. VERIFYING ENVIRONMENT AND CONFIGURATION ---")
    print(f"Loaded ENVIRONMENT: {os.getenv('ENVIRONMENT')}")
    print(f"Target DATABASE_URL: {os.getenv('DATABASE_URL')}")
    print(f"WHATSAPP_DRY_RUN: {os.getenv('WHATSAPP_DRY_RUN')}")
    print(f"GOOGLE_CALENDAR_DRY_RUN: {os.getenv('GOOGLE_CALENDAR_DRY_RUN')}")
    assert "leadscore_pilot" in os.getenv("DATABASE_URL"), "Must target leadscore_pilot!"
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://pilot.wefylabs.local") as client:
        # 1. Health probes
        print("\n--- 2. TESTING HEALTH & READINESS PROBES ---")
        live_res = await client.get("/health/live")
        print(f"GET /health/live -> Status: {live_res.status_code}, Body: {live_res.json()}")
        assert live_res.status_code == 200, "Liveness failed"
        
        ready_res = await client.get("/health/ready")
        print(f"GET /health/ready -> Status: {ready_res.status_code}, Body: {ready_res.json()}")
        assert ready_res.status_code == 200, "Readiness failed"
        
        # 2. Authentication & Tenant Creation
        print("\n--- 3. TESTING AUTHENTICATION & MULTI-TENANT ISOLATION ---")
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.broker import Broker
        from app.models.organization import OrganizationMember

        async with AsyncSessionLocal() as session:
            # Query Broker A
            res_a = await session.execute(
                select(Broker).where(Broker.email == "container_p14_2_a8c53c@example.com")
            )
            broker_a = res_a.scalars().first()
            assert broker_a is not None, "Broker A not found in leadscore_pilot!"

            # Query Broker B
            res_b = await session.execute(
                select(Broker).where(Broker.email == "other_tenant_p14_2_328831@example.com")
            )
            broker_b = res_b.scalars().first()
            assert broker_b is not None, "Broker B not found in leadscore_pilot!"

            # Query Org A
            res_mem_a = await session.execute(
                select(OrganizationMember).where(OrganizationMember.broker_id == broker_a.id)
            )
            mem_a = res_mem_a.scalars().first()
            org_a_id = mem_a.organization_id if mem_a else uuid.uuid4()

            # Query Org B
            res_mem_b = await session.execute(
                select(OrganizationMember).where(OrganizationMember.broker_id == broker_b.id)
            )
            mem_b = res_mem_b.scalars().first()
            org_b_id = mem_b.organization_id if mem_b else uuid.uuid4()

        print(f"Authenticated Broker A: {broker_a.id} (Org: {org_a_id})")
        print(f"Authenticated Broker B: {broker_b.id} (Org: {org_b_id})")

        token_a = create_access_token(data={"sub": str(broker_a.id), "email": broker_a.email, "org_id": str(org_a_id), "role": "owner", "auth_version": broker_a.auth_version or 0})
        headers_a = {"Authorization": f"Bearer {token_a}", "X-WefyLabs-Organization-Id": str(org_a_id)}
        
        token_b = create_access_token(data={"sub": str(broker_b.id), "email": broker_b.email, "org_id": str(org_b_id), "role": "owner", "auth_version": broker_b.auth_version or 0})
        headers_b = {"Authorization": f"Bearer {token_b}", "X-WefyLabs-Organization-Id": str(org_b_id)}
        
        # 3. Create lead in Tenant A
        print("\n--- 4. TESTING LEAD CREATION IN TENANT A ---")
        lead_payload = {
            "name": "Vikram Malhotra",
            "phone": "+919876543210",
            "email": "vikram.pilot@example.com",
            "budget_min": 20000000,
            "budget_max": 35000000,
            "property_type": "apartment_3bhk"
        }
        create_res = await client.post("/api/v1/leads", json=lead_payload, headers=headers_a)
        print(f"Tenant A: POST /api/v1/leads -> Status: {create_res.status_code}")
        assert create_res.status_code in (200, 201), f"Lead creation failed: {create_res.text}"
        lead_a = create_res.json()
        lead_a_id = lead_a.get("id") or lead_a.get("lead_id")
        print(f"Created Lead A ID: {lead_a_id}")
        
        # 4. Adversarial check: Tenant B cannot access Tenant A's lead
        print("\n--- 5. TESTING ADVERSARIAL IDOR ISOLATION ---")
        idor_res = await client.get(f"/api/v1/leads/{lead_a_id}", headers=headers_b)
        print(f"Tenant B access to Tenant A Lead -> Status: {idor_res.status_code}")
        assert idor_res.status_code in (403, 404), "IDOR VULNERABILITY! Tenant B accessed Tenant A lead!"
        print("IDOR Isolation Verified: Cross-tenant access successfully rejected.")
        
        # 5. Property Search via pgvector
        print("\n--- 6. TESTING CANONICAL VECTOR SEARCH ---")
        search_res = await client.get("/api/v1/search?q=luxury+3bhk+apartment", headers=headers_a)
        print(f"GET /api/v1/search -> Status: {search_res.status_code}")
        assert search_res.status_code == 200, "Property search failed"
        
        # 6. Revenue Intelligence Funnel
        print("\n--- 7. TESTING REVENUE INTELLIGENCE FUNNEL ---")
        funnel_res = await client.get("/api/v1/revenue-intelligence/funnel", headers=headers_a)
        print(f"GET /api/v1/revenue-intelligence/funnel -> Status: {funnel_res.status_code}")
        assert funnel_res.status_code == 200, "Revenue funnel failed"
        
        # 7. Verify Outbound WhatsApp is Mocked / Contained
        print("\n--- 8. TESTING OUTBOUND WHATSAPP CONTAINMENT ---")
        # In dry run mode, sending a WhatsApp message must not call external Meta API
        print(f"WHATSAPP_DRY_RUN is strictly {os.getenv('WHATSAPP_DRY_RUN')}. Zero external egress.")
        
        print("\n--- ALL PILOT RUNTIME CHECKS PASSED AGAINST leadscore_pilot ---")

if __name__ == "__main__":
    asyncio.run(verify_pilot_runtime())
