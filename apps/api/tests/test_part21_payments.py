"""
Part 21 — Customer Portal Payment Schedule & Proof Verification Tests
=====================================================================
Tests for:
1. Payment milestone schedule projection
2. Razorpay live gateway is strictly disabled (TEST/MOCK only)
3. Customer payment proof submission (sets REPORTED, never auto-verified)
4. Broker payment proof verification updates booking schedule
"""
import pytest
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.deal_models import Deal, DealBooking
from app.models.broker import Broker
from app.models.portal_models import CustomerPaymentProof
from app.modules.portal.service import CustomerPortalService
from app.modules.portal.dto.portal_schemas import (
    CustomerPaymentProofSubmitRequest
)


def _id():
    return uuid.uuid4()


class TestPaymentWorkflow:
    @pytest.mark.asyncio
    async def test_payment_schedule_and_razorpay_disabled_boundary(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        deal_id = _id()
        org_id = str(_id())

        deal = MagicMock(spec=Deal)
        deal.id = deal_id
        deal.currency = "AED"
        deal.agreed_price = Decimal("2000000.00")

        booking = MagicMock(spec=DealBooking)
        booking.payment_schedule = [
            {"name": "Booking Deposit", "amount": 200000, "status": "VERIFIED"},
            {"name": "Installment 1", "amount": 400000, "status": "DUE"},
            {"name": "Handover Balance", "amount": 1400000, "status": "UPCOMING"}
        ]
        deal.booking = booking

        res_deal = MagicMock(); res_deal.scalars().first.return_value = deal
        res_proofs = MagicMock(); res_proofs.scalars().all.return_value = []
        db.execute.side_effect = [res_deal, res_proofs]

        schedule = await svc.get_payments(str(lead_id), org_id)

        assert schedule.currency == "AED"
        assert schedule.total_payable == Decimal("2000000.00")
        assert schedule.total_verified == Decimal("200000.00")
        assert schedule.remaining_balance == Decimal("1800000.00")
        assert len(schedule.milestones) == 3
        assert schedule.milestones[0].status == "VERIFIED"
        assert schedule.milestones[1].status == "DUE"
        
        # NON-NEGOTIABLE PRINCIPLE 24: Razorpay live gateway must NEVER be enabled
        assert schedule.is_live_gateway_enabled is False

    @pytest.mark.asyncio
    async def test_submit_payment_proof_sets_reported_not_verified(self):
        """Customer uploading proof must set status to REPORTED, never VERIFIED."""
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        deal_id = _id()
        org_id = str(_id())

        deal = MagicMock(spec=Deal)
        deal.id = deal_id

        res_deal = MagicMock(); res_deal.scalars().first.return_value = deal
        db.execute.return_value = res_deal

        req = CustomerPaymentProofSubmitRequest(
            milestone_index=1,
            amount_reported=Decimal("400000.00"),
            currency="AED",
            payment_mode="bank_transfer",
            transaction_reference="WIRE-DXB-987654",
            receipt_url="https://storage.wefylabs.com/receipts/wire987.pdf",
            customer_notes="Transferred from Emirates NBD account."
        )

        proof = await svc.submit_payment_proof(str(lead_id), org_id, req)

        assert proof.status == "REPORTED"  # NEVER auto-verified
        assert proof.amount_reported == Decimal("400000.00")
        assert proof.transaction_reference == "WIRE-DXB-987654"
        assert db.add.called
        assert db.commit.called

    @pytest.mark.asyncio
    async def test_broker_verify_payment_proof_updates_booking_schedule(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        broker_mock = MagicMock(spec=Broker)
        broker_mock.id = _id()

        proof_id = _id()
        deal_id = _id()

        proof = MagicMock(spec=CustomerPaymentProof)
        proof.id = proof_id
        proof.deal_id = deal_id
        proof.milestone_index = 1
        proof.status = "REPORTED"

        deal = MagicMock(spec=Deal)
        deal.id = deal_id
        booking = MagicMock(spec=DealBooking)
        booking.payment_schedule = [
            {"name": "Booking Deposit", "amount": 200000, "status": "VERIFIED"},
            {"name": "Installment 1", "amount": 400000, "status": "REPORTED"},
            {"name": "Handover Balance", "amount": 1400000, "status": "UPCOMING"}
        ]
        deal.booking = booking

        res_proof = MagicMock(); res_proof.scalars().first.return_value = proof
        res_deal = MagicMock(); res_deal.scalars().first.return_value = deal
        db.execute.side_effect = [res_proof, res_deal]

        result = await svc.review_payment_proof(broker_mock, str(proof_id), "VERIFY", review_notes="Wire verified in bank account.")

        assert result["status"] == "VERIFIED"
        assert proof.status == "VERIFIED"
        assert proof.reviewed_by_id == str(broker_mock.id)
        assert booking.payment_schedule[1]["status"] == "VERIFIED"
        assert db.commit.called
