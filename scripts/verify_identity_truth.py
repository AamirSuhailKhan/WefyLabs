import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add apps/api to path
api_dir = Path("apps/api").resolve()
sys.path.insert(0, str(api_dir))

from dotenv import load_dotenv
load_dotenv('apps/api/.env')

import jwt
from fastapi import HTTPException
from app.config import settings
from app.database import AsyncSessionLocal
from app.dependencies import get_current_broker, get_current_tenant, TenantContext
from app.models.broker import Broker
from app.models.organization import OrganizationMember

async def test_identity_chain():
    print("=== TESTING CANONICAL IDENTITY CHAIN ===")
    
    # 1. Inspect authenticated broker Aamir Suhail
    broker_id = uuid.UUID("c193be18-4a6a-4030-9089-f94c42119189")
    org_id = uuid.UUID("a0317351-e076-493e-8b84-182f8c43666e")
    other_org_id = uuid.UUID("5651f9f3-2a17-4261-8b22-1989887e25d1") # Test Agency

    async with AsyncSessionLocal() as db:
        # Generate valid JWT token for Aamir Suhail
        payload = {
            "sub": str(broker_id),
            "email": "aamir.fresh@bmu.edu.in",
            "iat": 1728000000,
            "exp": 1828000000
        }
        token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
        
        # Test 1: get_current_broker
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        broker = await get_current_broker(credentials=creds, db=db)
        assert broker.id == broker_id, f"Expected {broker_id}, got {broker.id}"
        print(f"[PASS] 1. Token -> Verified Broker: {broker.name} ({broker.email}) [ID: {broker.id}]")

        # Test 2: get_current_tenant with valid org header
        ctx = await get_current_tenant(current_broker=broker, db=db, requested_organization_id=str(org_id))
        assert ctx.organization_id == str(org_id)
        assert ctx.broker_id == broker_id
        assert ctx.role == "OWNER"
        print(f"[PASS] 2. Verified Broker -> Canonical Tenant: {ctx.organization_id} (Role: {ctx.role})")

        # Test 3: get_current_tenant with spoofed unauthorized org header
        try:
            await get_current_tenant(current_broker=broker, db=db, requested_organization_id=str(other_org_id))
            print("[FAIL] Spoofed org was accepted!")
        except HTTPException as exc:
            assert exc.status_code == 403
            assert exc.detail["code"] == "ORGANIZATION_ACCESS_DENIED"
            print(f"[PASS] 3. Spoofed Org ID ({other_org_id}) Rejected with 403 ORGANIZATION_ACCESS_DENIED")

        # Test 4: get_current_tenant with malformed UUID org header
        try:
            await get_current_tenant(current_broker=broker, db=db, requested_organization_id="not-a-valid-uuid")
            print("[FAIL] Malformed UUID was accepted!")
        except HTTPException as exc:
            assert exc.status_code == 400
            assert exc.detail["code"] == "INVALID_ORGANIZATION_CONTEXT"
            print("[PASS] 4. Malformed Org ID Rejected with 400 INVALID_ORGANIZATION_CONTEXT")

        # Test 5: get_current_tenant without header (single membership auto-select)
        ctx_default = await get_current_tenant(current_broker=broker, db=db, requested_organization_id=None)
        assert ctx_default.organization_id == str(org_id)
        print(f"[PASS] 5. No Header -> Auto-selected Sole Organization: {ctx_default.organization_id}")

    print("\nALL IDENTITY CHAIN TESTS PASSED!")

if __name__ == '__main__':
    asyncio.run(test_identity_chain())
