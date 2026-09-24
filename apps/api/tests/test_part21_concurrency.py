"""
Part 21 — Concurrency & Idempotency Tests
========================================
Tests for:
1. Idempotent payment proof submission under network retries
2. Concurrent document upload handling
3. Appointment confirmation idempotency
"""
import pytest
import asyncio
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.models.deal_models import Deal
from app.models.portal_models import CustomerPaymentProof
from app.modules.portal.service import CustomerPortalService
from app.modules.portal.dto.portal_schemas import (
    CustomerPaymentProofSubmitRequest
)


def _id():
    return uuid.uuid4()


class TestCustomerPortalConcurrency:
    @pytest.mark.asyncio
    async def test_duplicate_payment_proof_submission_idempotency(self):
        """Duplicate request with same idempotency_key must return existing record without duplicate insertion."""
        db = AsyncMock()
        svc = CustomerPortalService(db)

        lead_id = _id()
        deal_id = _id()
        org_id = str(_id())
        idem_key = f"idem-proof-{_id()}"

        deal = MagicMock(spec=Deal)
        deal.id = deal_id

        existing_proof = MagicMock(spec=CustomerPaymentProof)
        existing_proof.id = _id()
        existing_proof.idempotency_key = idem_key
        existing_proof.status = "REPORTED"

        # First call finds deal, then finds existing proof with this idempotency key
        res_deal = MagicMock(); res_deal.scalars().first.return_value = deal
        res_proof = MagicMock(); res_proof.scalars().first.return_value = existing_proof
        db.execute.side_effect = [res_deal, res_proof]

        req = CustomerPaymentProofSubmitRequest(
            milestone_index=0,
            amount_reported=Decimal("150000.00"),
            currency="AED",
            payment_mode="bank_transfer",
            transaction_reference="REF-DUP-1",
            receipt_url="https://cdn.wefylabs.com/receipt.pdf",
            idempotency_key=idem_key
        )

        result = await svc.submit_payment_proof(str(lead_id), org_id, req)

        assert result == existing_proof
        # Ensure db.add was NOT called because it was deduplicated
        assert db.add.called is False
