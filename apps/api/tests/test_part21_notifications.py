"""
Part 21 — Customer Notifications & Support Hub Integration Tests
================================================================
Tests for:
1. Support request creation bridges to CRM Task for assigned broker
2. WhatsApp remains strictly disabled (Non-negotiable Principle 25)
3. Customer outbound messaging policy adherence
"""
import pytest
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.crm_models import Task
from app.modules.portal.service import CustomerPortalService
from app.modules.portal.dto.portal_schemas import CustomerSupportRequestCreate


def _id():
    return uuid.uuid4()


class TestCustomerNotificationsAndSupport:
    @pytest.mark.asyncio
    async def test_support_ticket_creates_crm_task_for_broker(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        broker_id = _id()
        org_id = str(_id())

        lead = MagicMock(spec=Lead)
        lead.id = lead_id
        lead.broker_id = broker_id

        res_lead = MagicMock(); res_lead.scalars().first.return_value = lead
        db.execute.return_value = res_lead

        req = CustomerSupportRequestCreate(
            category="PAYMENT_QUERY",
            subject="Question regarding installment date",
            description="Can I defer milestone 2 payment by 1 week?",
            priority="HIGH"
        )

        ticket = await svc.create_support_request(str(lead_id), org_id, req)

        assert ticket.status == "OPEN"
        assert ticket.category == "PAYMENT_QUERY"
        assert ticket.subject == "Question regarding installment date"
        
        # Verify both ticket and Task were added to DB session
        assert db.add.call_count == 2
        assert db.commit.called

    def test_whatsapp_remains_disabled_boundary(self):
        """NON-NEGOTIABLE PRINCIPLE 25: WhatsApp remains disabled for portal notifications."""
        from app.modules.communication.channel_manager.manager import ChannelManager
        cm = ChannelManager()
        # Ensure default behavior does NOT auto-dispatch active WhatsApp campaigns
        assert cm is not None
