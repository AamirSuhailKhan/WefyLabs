"""
Part 21 — Full End-to-End Customer Transaction Journey Test
===========================================================
Tests complete multi-actor flow:
1. Broker invites customer to portal
2. Customer exchanges invite token for authenticated session JWT
3. Customer inspects deal room
4. Customer uploads document -> IN_REVIEW
5. Broker approves document -> APPROVED
6. Customer submits payment proof -> REPORTED
7. Broker reviews & verifies payment proof -> VERIFIED
8. Customer submits CSAT & NPS post-sale feedback
"""
import pytest
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.models.deal_models import Deal, DealDocument, DealBooking
from app.models.lead import Lead
from app.models.broker import Broker
from app.models.portal_models import CustomerPortalInvite, CustomerPaymentProof
from app.modules.portal.service import CustomerPortalService, _hash_token
from app.modules.portal.dto.portal_schemas import (
    CustomerDocumentUploadRequest,
    CustomerPaymentProofSubmitRequest,
    CustomerPostSaleFeedbackRequest
)


def _id():
    return uuid.uuid4()


class TestCustomerJourneyE2E:
    @pytest.mark.asyncio
    async def test_full_customer_deal_lifecycle(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        broker_id = _id()
        deal_id = _id()
        org_id = str(broker_id)

        # ── Step 1: Broker generates invite ──────────────────────────────────
        lead = MagicMock(spec=Lead)
        lead.id = lead_id
        lead.broker_id = broker_id
        lead.name = "Vikram Malhotra"
        lead.email = "vikram@example.com"
        lead.phone = "+971521234567"

        broker = MagicMock(spec=Broker)
        broker.id = broker_id
        broker.organization_id = org_id
        broker.name = "Alexander Wright"
        broker.agency_name = "Prime Properties Dubai"
        broker.email = "alex@wefylabs.com"
        broker.phone = "+971501112233"

        res_lead = MagicMock(); res_lead.scalars().first.return_value = lead
        db.execute.return_value = res_lead

        invite_res = await svc.generate_portal_invite(broker, str(lead_id), deal_id=str(deal_id))
        assert invite_res.raw_token is not None
        assert invite_res.lead_id == str(lead_id)

        # ── Step 2: Customer exchanges invite token for JWT ─────────────────
        raw_token = invite_res.raw_token
        invite_mock = MagicMock(spec=CustomerPortalInvite)
        invite_mock.token_hash = _hash_token(raw_token)
        invite_mock.status = "active"
        invite_mock.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        invite_mock.lead_id = lead_id
        invite_mock.organization_id = org_id
        invite_mock.access_count = 0

        res_inv = MagicMock(); res_inv.scalars().first.return_value = invite_mock
        res_lead2 = MagicMock(); res_lead2.scalars().first.return_value = lead
        db.execute.side_effect = [res_inv, res_lead2]

        auth_res = await svc.exchange_invite_token(raw_token)
        assert auth_res.access_token is not None
        assert auth_res.customer_id == str(lead_id)
        assert auth_res.customer_name == "Vikram Malhotra"

        # ── Step 3: Customer uploads required document ──────────────────────
        doc_id = _id()
        doc = MagicMock(spec=DealDocument)
        doc.id = doc_id
        doc.document_type = "EMIRATES_ID"
        doc.document_name = "Emirates ID"
        doc.required_at_stage = "BOOKING"
        doc.is_required = True
        doc.status = "REQUIRED"
        doc.rejection_reason = None

        res_doc = MagicMock(); res_doc.scalars().first.return_value = doc
        db.execute.side_effect = None
        db.execute.return_value = res_doc

        upload_req = CustomerDocumentUploadRequest(file_url="https://storage.wefylabs.com/eid_vikram.pdf")
        uploaded_doc = await svc.upload_document(str(lead_id), org_id, str(doc_id), upload_req)

        assert uploaded_doc.customer_status == "IN_REVIEW"
        assert doc.status == "UPLOADED"

        # ── Step 4: Broker reviews & approves document ──────────────────────
        res_doc_rev = MagicMock(); res_doc_rev.scalars().first.return_value = doc
        db.execute.return_value = res_doc_rev

        rev_res = await svc.review_document(broker, str(doc_id), "APPROVE")
        assert rev_res["status"] == "VERIFIED"
        assert doc.status == "VERIFIED"

        # ── Step 5: Customer submits payment proof ──────────────────────────
        deal = MagicMock(spec=Deal)
        deal.id = deal_id
        booking = MagicMock(spec=DealBooking)
        booking.payment_schedule = [
            {"name": "Booking Deposit", "amount": 250000, "status": "VERIFIED"},
            {"name": "Installment 1", "amount": 500000, "status": "DUE"}
        ]
        deal.booking = booking
        deal.post_sale_record = None

        res_deal_p = MagicMock(); res_deal_p.scalars().first.return_value = deal
        db.execute.return_value = res_deal_p

        proof_req = CustomerPaymentProofSubmitRequest(
            milestone_index=1,
            amount_reported=Decimal("500000.00"),
            currency="AED",
            payment_mode="wire",
            transaction_reference="WIRE-VIK-1002",
            receipt_url="https://storage.wefylabs.com/receipts/wire1002.pdf"
        )
        proof = await svc.submit_payment_proof(str(lead_id), org_id, proof_req)
        assert proof.status == "REPORTED"

        # ── Step 6: Broker verifies payment proof ───────────────────────────
        proof_mock = MagicMock(spec=CustomerPaymentProof)
        proof_mock.id = _id()
        proof_mock.deal_id = deal_id
        proof_mock.milestone_index = 1
        proof_mock.status = "REPORTED"

        res_pf = MagicMock(); res_pf.scalars().first.return_value = proof_mock
        res_dl = MagicMock(); res_dl.scalars().first.return_value = deal
        db.execute.side_effect = [res_pf, res_dl]

        verify_res = await svc.review_payment_proof(broker, str(proof_mock.id), "VERIFY")
        assert verify_res["status"] == "VERIFIED"
        assert booking.payment_schedule[1]["status"] == "VERIFIED"

        # ── Step 7: Customer submits CSAT & NPS feedback ────────────────────
        res_deal_fb = MagicMock(); res_deal_fb.scalars().first.return_value = deal
        db.execute.side_effect = None
        db.execute.return_value = res_deal_fb

        fb_req = CustomerPostSaleFeedbackRequest(
            csat_score=5,
            nps_score=10,
            feedback_text="Outstanding seamless transaction experience through the deal room!",
            referral_interested=True
        )
        fb_res = await svc.submit_post_sale_feedback(str(lead_id), org_id, fb_req)
        assert fb_res.status == "RECORDED"
        assert "Thank you" in fb_res.message
