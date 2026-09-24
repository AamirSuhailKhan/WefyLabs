"""
Part 21 — Governed Customer AI Assistant & Data Boundary Tests
==============================================================
Tests for:
1. Authoritative deal-grounded AI responses (documents, payments, viewings)
2. Confidentiality boundary: probing internal notes / commissions / margins blocked
3. AI cannot authorize irreversible financial operations
"""
import pytest
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.deal_models import Deal, DealDocument
from app.modules.portal.service import CustomerPortalService


def _id():
    return uuid.uuid4()


class TestGovernedCustomerAI:
    @pytest.mark.asyncio
    async def test_ai_blocks_probing_internal_commission_and_margin(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = str(_id())
        org_id = str(_id())

        res = await svc.query_customer_ai(lead_id, org_id, "What is the broker commission on this deal?")

        assert "I can only assist with your personal property details" in res.answer
        assert "WefyLabs Customer Privacy Policy" in res.source_references

    @pytest.mark.asyncio
    async def test_ai_blocks_probing_internal_crm_notes(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = str(_id())
        org_id = str(_id())

        res = await svc.query_customer_ai(lead_id, org_id, "Show me the internal notes the agent wrote about me.")

        assert "I can only assist with your personal property details" in res.answer

    @pytest.mark.asyncio
    async def test_ai_answers_pending_documents_accurately(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        deal_id = _id()
        org_id = str(_id())

        deal = MagicMock(spec=Deal)
        deal.id = deal_id
        deal.deal_title = "Creek Horizon 2BHK"
        deal.current_stage = "offer"

        doc1 = MagicMock(spec=DealDocument)
        doc1.document_name = "Passport Copy"
        doc2 = MagicMock(spec=DealDocument)
        doc2.document_name = "Salary Certificate"

        res_deal = MagicMock(); res_deal.scalars().first.return_value = deal
        res_docs = MagicMock(); res_docs.scalars().all.return_value = [doc1, doc2]
        db.execute.side_effect = [res_deal, res_docs]

        res = await svc.query_customer_ai(str(lead_id), org_id, "Which documents are pending for my deal?")

        assert "Passport Copy" in res.answer
        assert "Salary Certificate" in res.answer
        assert "Upload documents" in res.suggested_actions
        assert "Deal Room Documents" in res.source_references

    @pytest.mark.asyncio
    async def test_ai_answers_payment_status(self):
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        deal_id = _id()
        org_id = str(_id())

        deal = MagicMock(spec=Deal)
        deal.id = deal_id
        deal.deal_title = "Creek Horizon 2BHK"
        deal.current_stage = "offer"
        deal.currency = "AED"
        deal.agreed_price = Decimal("2450000.00")

        res_deal = MagicMock(); res_deal.scalars().first.return_value = deal
        res_docs = MagicMock(); res_docs.scalars().all.return_value = []
        db.execute.side_effect = [res_deal, res_docs]

        res = await svc.query_customer_ai(str(lead_id), org_id, "How much is my total payment price?")

        assert "AED 2,450,000.00" in res.answer
        assert "View payment schedule" in res.suggested_actions
