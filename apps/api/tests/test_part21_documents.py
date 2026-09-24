"""
Part 21 — Customer Portal Document Workflow Tests
=================================================
Tests for:
1. Customer-safe status mapping (ACTION_REQUIRED, IN_REVIEW, APPROVED)
2. Customer document upload
3. Broker review & approval workflow
4. Broker rejection with feedback
"""
import pytest
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.deal_models import Deal, DealDocument
from app.models.broker import Broker
from app.modules.portal.service import CustomerPortalService
from app.modules.portal.dto.portal_schemas import (
    CustomerDocumentUploadRequest
)


def _id():
    return uuid.uuid4()


class TestDocumentWorkflow:
    @pytest.mark.asyncio
    async def test_document_listing_customer_safe_status_mapping(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        deal_id = _id()
        org_id = str(_id())

        doc1 = MagicMock(spec=DealDocument)
        doc1.id = _id(); doc1.document_type = "KYC_PASSPORT"; doc1.document_name = "Passport"; doc1.required_at_stage = "offer"; doc1.is_required = True; doc1.status = "REQUIRED"; doc1.file_url = None; doc1.uploaded_at = None; doc1.verified_at = None; doc1.rejection_reason = None

        doc2 = MagicMock(spec=DealDocument)
        doc2.id = _id(); doc2.document_type = "BOOKING_FORM"; doc2.document_name = "Booking Form"; doc2.required_at_stage = "booking"; doc2.is_required = True; doc2.status = "UPLOADED"; doc2.file_url = "https://cdn.wefylabs.com/bk.pdf"; doc2.uploaded_at = datetime.now(timezone.utc); doc2.verified_at = None; doc2.rejection_reason = None

        doc3 = MagicMock(spec=DealDocument)
        doc3.id = _id(); doc3.document_type = "TITLE_DEED"; doc3.document_name = "Title Deed"; doc3.required_at_stage = "closing"; doc3.is_required = True; doc3.status = "VERIFIED"; doc3.file_url = "https://cdn.wefylabs.com/td.pdf"; doc3.uploaded_at = datetime.now(timezone.utc); doc3.verified_at = datetime.now(timezone.utc); doc3.rejection_reason = None

        doc4 = MagicMock(spec=DealDocument)
        doc4.id = _id(); doc4.document_type = "PROOF_OF_ADDRESS"; doc4.document_name = "Utility Bill"; doc4.required_at_stage = "offer"; doc4.is_required = True; doc4.status = "REJECTED"; doc4.file_url = "https://cdn.wefylabs.com/bill.pdf"; doc4.uploaded_at = datetime.now(timezone.utc); doc4.verified_at = None; doc4.rejection_reason = "Document is blurry. Please upload clear scan."

        res_deal_id = MagicMock(); res_deal_id.scalar.return_value = deal_id
        res_docs = MagicMock(); res_docs.scalars().all.return_value = [doc1, doc2, doc3, doc4]
        db.execute.side_effect = [res_deal_id, res_docs]

        docs = await svc.get_documents(str(lead_id), org_id)

        assert len(docs) == 4
        assert docs[0].customer_status == "ACTION_REQUIRED"
        assert docs[1].customer_status == "IN_REVIEW"
        assert docs[2].customer_status == "APPROVED"
        assert docs[3].customer_status == "ACTION_REQUIRED"
        assert docs[3].rejection_reason == "Document is blurry. Please upload clear scan."

    @pytest.mark.asyncio
    async def test_customer_document_upload_sets_in_review(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        doc_id = _id()
        org_id = str(_id())

        doc = MagicMock(spec=DealDocument)
        doc.id = doc_id
        doc.document_type = "EMIRATES_ID"
        doc.document_name = "Emirates ID"
        doc.required_at_stage = "offer"
        doc.is_required = True
        doc.status = "REQUIRED"
        doc.rejection_reason = "Previously expired"

        res = MagicMock(); res.scalars().first.return_value = doc
        db.execute.return_value = res

        req = CustomerDocumentUploadRequest(file_url="https://cdn.wefylabs.com/eid_new.pdf")
        updated_doc = await svc.upload_document(str(lead_id), org_id, str(doc_id), req)

        assert updated_doc.customer_status == "IN_REVIEW"
        assert updated_doc.file_url == "https://cdn.wefylabs.com/eid_new.pdf"
        assert doc.status == "UPLOADED"
        assert doc.rejection_reason is None  # cleared
        assert db.commit.called

    @pytest.mark.asyncio
    async def test_broker_review_approve_document(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        broker_mock = MagicMock(spec=Broker)
        broker_mock.id = _id()

        doc_id = _id()
        doc = MagicMock(spec=DealDocument)
        doc.id = doc_id
        doc.status = "UPLOADED"

        res = MagicMock(); res.scalars().first.return_value = doc
        db.execute.return_value = res

        result = await svc.review_document(broker_mock, str(doc_id), "APPROVE")

        assert result["status"] == "VERIFIED"
        assert doc.status == "VERIFIED"
        assert doc.verified_at is not None
        assert doc.verified_by_id == str(broker_mock.id)
        assert db.commit.called

    @pytest.mark.asyncio
    async def test_broker_review_reject_document(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        broker_mock = MagicMock(spec=Broker)
        broker_mock.id = _id()

        doc_id = _id()
        doc = MagicMock(spec=DealDocument)
        doc.id = doc_id
        doc.status = "UPLOADED"

        res = MagicMock(); res.scalars().first.return_value = doc
        db.execute.return_value = res

        result = await svc.review_document(broker_mock, str(doc_id), "REJECT", rejection_reason="Signature missing on page 2")

        assert result["status"] == "REJECTED"
        assert doc.status == "REJECTED"
        assert doc.rejection_reason == "Signature missing on page 2"
        assert db.commit.called
