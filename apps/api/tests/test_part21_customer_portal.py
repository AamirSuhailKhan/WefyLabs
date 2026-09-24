"""
Part 21 — Customer Portal & Deal Room Unit & Contract Tests
===========================================================
Tests for:
- Customer overview aggregation
- Digital deal room projection (9 stages)
- Property summary projection
- Next action resolution
- Acknowledgements
"""
import pytest
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.models.deal_models import Deal, DealOffer, DealReservation, DealBooking, DealClosing, DealDocument
from app.models.lead import Lead
from app.models.broker import Broker
from app.modules.portal.service import CustomerPortalService
from app.modules.portal.dto.portal_schemas import (
    CustomerAcknowledgementRequest
)


def _id():
    return uuid.uuid4()


class TestCustomerPortalOverview:
    @pytest.mark.asyncio
    async def test_portal_overview_with_active_deal_and_pending_docs(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        broker_id = _id()
        org_id = str(_id())

        lead_mock = MagicMock(spec=Lead)
        lead_mock.id = lead_id
        lead_mock.broker_id = broker_id
        lead_mock.name = "Aamir Khan"
        lead_mock.email = "aamir@example.com"
        lead_mock.phone = "+971501234567"

        broker_mock = MagicMock(spec=Broker)
        broker_mock.id = broker_id
        broker_mock.name = "Sarah Jenkins"
        broker_mock.agency_name = "Luxury Dubai Realty"
        broker_mock.email = "sarah@wefylabs.com"
        broker_mock.phone = "+971509998877"

        deal_mock = MagicMock(spec=Deal)
        deal_mock.id = _id()
        deal_mock.deal_reference = "DEAL-DXB-101"
        deal_mock.deal_title = "Downtown Luxury Penthouse"
        deal_mock.current_stage = "offer"
        deal_mock.agreed_price = Decimal("3500000.00")
        deal_mock.currency = "AED"
        deal_mock.status = "ACTIVE"
        deal_mock.booking = None
        deal_mock.post_sale_record = None

        doc_mock = MagicMock(spec=DealDocument)
        doc_mock.id = _id()
        doc_mock.document_name = "Passport Copy"
        doc_mock.status = "REQUIRED"

        # Mock query executions sequentially
        res1 = MagicMock(); res1.scalars().first.return_value = lead_mock
        res2 = MagicMock(); res2.scalars().first.return_value = broker_mock
        res3 = MagicMock(); res3.scalars().first.return_value = deal_mock
        res4 = MagicMock(); res4.scalars().all.return_value = [doc_mock]
        res5 = MagicMock(); res5.scalar.return_value = 1  # 1 upcoming meeting
        res6 = MagicMock(); res6.scalars().first.return_value = None  # conversation

        db.execute.side_effect = [res1, res2, res3, res4, res5, res6]

        overview = await svc.get_portal_overview(str(lead_id), org_id)

        assert overview.customer_name == "Aamir Khan"
        assert overview.assigned_advisor is not None
        assert overview.assigned_advisor.name == "Sarah Jenkins"
        assert overview.active_deal is not None
        assert overview.active_deal.deal_reference == "DEAL-DXB-101"
        assert overview.pending_documents_count == 1
        assert overview.next_action.action_type == "UPLOAD_DOCUMENT"
        assert "Passport Copy" in overview.next_action.title
        assert overview.next_action.is_urgent is True

    @pytest.mark.asyncio
    async def test_portal_deal_room_sanitized_projection(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        deal_id = _id()
        org_id = str(_id())

        deal_mock = MagicMock(spec=Deal)
        deal_mock.id = deal_id
        deal_mock.deal_reference = "DEAL-DXB-202"
        deal_mock.deal_title = "Palm Jumeirah Villa"
        deal_mock.current_stage = "booking"
        deal_mock.currency = "AED"
        deal_mock.agreed_price = Decimal("12500000.00")
        deal_mock.status = "ACTIVE"
        deal_mock.property_listing = None
        deal_mock.offer = None
        deal_mock.reservation = None
        deal_mock.stage_entered_at = datetime.now(timezone.utc)

        # Booking mock
        booking_mock = MagicMock(spec=DealBooking)
        booking_mock.booking_reference = "BK-202-001"
        booking_mock.token_amount = Decimal("100000.00")
        booking_mock.token_paid_at = datetime.now(timezone.utc)
        booking_mock.booked_price = Decimal("12500000.00")
        booking_mock.currency = "AED"
        booking_mock.payment_plan_type = "40/60"
        booking_mock.status = "CONFIRMED"
        booking_mock.booked_at = datetime.now(timezone.utc)
        deal_mock.booking = booking_mock
        deal_mock.closing_record = None

        res_deal = MagicMock(); res_deal.scalars().first.return_value = deal_mock
        res_ack = MagicMock(); res_ack.scalars().first.return_value = None
        db.execute.side_effect = [res_deal, res_ack]

        deal_room = await svc.get_deal_room(str(lead_id), org_id, deal_id=str(deal_id))

        assert deal_room.deal_reference == "DEAL-DXB-202"
        assert deal_room.booking is not None
        assert deal_room.booking.booking_reference == "BK-202-001"
        assert len(deal_room.stages_timeline) == 9
        
        # Verify booking stage is current
        booking_step = [s for s in deal_room.stages_timeline if s.stage_key == "booking"][0]
        assert booking_step.is_current is True

        # Verify stages before booking are marked completed
        opp_step = [s for s in deal_room.stages_timeline if s.stage_key == "opportunity"][0]
        assert opp_step.is_completed is True

        # Verify stages after booking are not completed
        closing_step = [s for s in deal_room.stages_timeline if s.stage_key == "closing"][0]
        assert closing_step.is_completed is False

    @pytest.mark.asyncio
    async def test_record_transaction_acknowledgement(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        deal_id = _id()
        org_id = str(_id())

        res_deal = MagicMock(); res_deal.scalar.return_value = deal_id
        db.execute.return_value = res_deal

        req = CustomerAcknowledgementRequest(
            acknowledgement_type="BOOKING_SUMMARY",
            item_version="v2.1"
        )
        res = await svc.record_acknowledgement(str(lead_id), org_id, req, ip="192.168.1.1", ua="Chrome/128")

        assert res["status"] == "ACKNOWLEDGED"
        assert "acknowledged_at" in res
        assert db.add.called
        assert db.commit.called
