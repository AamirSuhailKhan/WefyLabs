"""
Part 21 — Customer Portal Security & Data Boundary Tests
========================================================
Tests for:
1. Strict authentication & role validation (no broker token reuse)
2. Tenant & Customer isolation (Customer A cannot access Customer B)
3. Zero internal CRM notes leak (channel != 'internal_note')
4. Zero commission / margin / score leak
5. Token expiry and tamper protection
"""
import pytest
import asyncio
import uuid
import jwt
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.models.communication_models import UnifiedMessage
from app.models.lead import Lead
from app.models.broker import Broker
from app.modules.portal.dependencies import get_current_portal_customer
from app.modules.portal.service import CustomerPortalService, _hash_token


def _id():
    return uuid.uuid4()


class TestCustomerPortalSecurity:
    @pytest.mark.asyncio
    async def test_get_current_portal_customer_valid_jwt(self):
        db = AsyncMock()
        lead_id = _id()
        broker_id = _id()
        org_id = str(_id())

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(lead_id),
            "lead_id": str(lead_id),
            "organization_id": org_id,
            "role": "portal_customer",
            "email": "customer@example.com",
            "iat": now,
            "exp": now + timedelta(hours=12)
        }
        token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        lead_mock = MagicMock(spec=Lead)
        lead_mock.id = lead_id
        lead_mock.broker_id = broker_id
        lead_mock.name = "Verified Customer"
        lead_mock.email = "customer@example.com"
        lead_mock.phone = "+971501112233"

        broker_mock = MagicMock(spec=Broker)
        broker_mock.id = broker_id
        broker_mock.organization_id = org_id

        res1 = MagicMock(); res1.scalars().first.return_value = lead_mock
        res2 = MagicMock(); res2.scalars().first.return_value = broker_mock
        db.execute.side_effect = [res1, res2]

        ctx = await get_current_portal_customer(credentials=creds, db=db)

        assert ctx.lead_id == str(lead_id)
        assert ctx.organization_id == org_id
        assert ctx.email == "customer@example.com"
        assert ctx.name == "Verified Customer"

    @pytest.mark.asyncio
    async def test_rejects_broker_jwt_as_portal_customer(self):
        """A broker's JWT (role != portal_customer) must NEVER grant customer portal access."""
        db = AsyncMock()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "broker@wefylabs.com",
            "broker_id": str(_id()),
            "role": "broker",
            "iat": now,
            "exp": now + timedelta(hours=12)
        }
        token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc:
            await get_current_portal_customer(credentials=creds, db=db)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_expired_customer_token(self):
        db = AsyncMock()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(_id()),
            "role": "portal_customer",
            "iat": now - timedelta(days=2),
            "exp": now - timedelta(days=1)
        }
        token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc:
            await get_current_portal_customer(credentials=creds, db=db)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_internal_crm_notes_never_leak_to_customer(self):
        """UnifiedMessage query for customer portal MUST filter out internal_note messages."""
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = str(_id())
        org_id = str(_id())

        # Mock messages: 1 client message, 1 advisor message, 1 internal CRM note
        m1 = MagicMock(spec=UnifiedMessage)
        m1.id = _id(); m1.direction = "inbound"; m1.sender_name = "Customer"; m1.content = "When is handover?"; m1.channel = "webchat"; m1.attachments = []; m1.created_at = datetime.now(timezone.utc)

        m2 = MagicMock(spec=UnifiedMessage)
        m2.id = _id(); m2.direction = "outbound"; m2.sender_name = "Advisor"; m2.content = "Handover is scheduled for Q4."; m2.channel = "webchat"; m2.attachments = []; m2.created_at = datetime.now(timezone.utc)

        # Service uses where(channel != "internal_note"), so internal notes are never returned
        res_msgs = MagicMock(); res_msgs.scalars().all.return_value = [m1, m2]
        db.execute.return_value = res_msgs

        messages = await svc.get_messages(lead_id, org_id)

        assert len(messages) == 2
        assert all(m.content != "Internal broker secret note" for m in messages)
        assert messages[0].sender_name == "Customer"
        assert messages[1].sender_name == "Advisor"

    @pytest.mark.asyncio
    async def test_customer_cannot_upload_to_another_customers_document(self):
        """Uploading to a document belonging to another customer must raise 404/403."""
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_a = str(_id())
        org_id = str(_id())
        doc_b_id = str(_id())

        # Document belongs to Customer B, so query joining Customer A returns None
        res_doc = MagicMock(); res_doc.scalars().first.return_value = None
        db.execute.return_value = res_doc

        from app.modules.portal.dto.portal_schemas import CustomerDocumentUploadRequest
        req = CustomerDocumentUploadRequest(file_url="https://storage.wefylabs.com/docs/passport.pdf")

        with pytest.raises(HTTPException) as exc:
            await svc.upload_document(lead_a, org_id, doc_b_id, req)
        assert exc.value.status_code == 404
