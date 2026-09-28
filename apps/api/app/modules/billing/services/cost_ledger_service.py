"""
WefyLabs Canonical Cost Ledger Service
======================================
Captures direct variable costs incurred per organization:
- AI tokens (input/output tokens by model)
- WhatsApp / SMS messaging fees
- Payment gateway processing fees (Razorpay)
- Cloud compute & storage GB-day costs
- Third-party API charges
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_models import CostEvent
from app.modules.billing.domain.money import Money

logger = logging.getLogger("wefylabs.billing.cost_ledger")

# Default unit pricing benchmarks (USD)
DEFAULT_COST_BENCHMARKS = {
    "gpt-4o-mini-input": Decimal("0.00000015"),   # $0.15 / 1M tokens
    "gpt-4o-mini-output": Decimal("0.00000060"),  # $0.60 / 1M tokens
    "claude-3-5-sonnet-input": Decimal("0.00000300"), # $3.00 / 1M tokens
    "claude-3-5-sonnet-output": Decimal("0.00001500"), # $15.00 / 1M tokens
    "whatsapp-session-in": Decimal("0.0050"),     # $0.005 / inbound conversation
    "whatsapp-marketing-out": Decimal("0.0120"),  # $0.012 / outbound template
    "storage-gb-day": Decimal("0.00076"),         # $0.023 / GB-month
}


class CostLedgerService:
    """
    Append-only cost event ledger.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log_ai_cost(
        self,
        organization_id: uuid.UUID,
        model: str,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_usd: Optional[Decimal] = None,
        source_request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CostEvent:
        """
        Logs token consumption and direct vendor cost for an AI inference call.
        """
        now = datetime.now(timezone.utc)
        total_tokens = input_tokens + output_tokens

        if estimated_cost_usd is not None:
            total_cost = estimated_cost_usd
            unit_cost = (total_cost / Decimal(total_tokens)) if total_tokens > 0 else Decimal("0.0")
        else:
            in_rate = DEFAULT_COST_BENCHMARKS.get(f"{model}-input", Decimal("0.0000005"))
            out_rate = DEFAULT_COST_BENCHMARKS.get(f"{model}-output", Decimal("0.0000020"))
            total_cost = (Decimal(input_tokens) * in_rate) + (Decimal(output_tokens) * out_rate)
            unit_cost = (total_cost / Decimal(total_tokens)) if total_tokens > 0 else Decimal("0.0")

        event = CostEvent(
            organization_id=organization_id,
            service="AI",
            vendor="OPENAI" if "gpt" in model else ("ANTHROPIC" if "claude" in model else "VENDOR"),
            unit="TOKENS",
            quantity=Decimal(total_tokens),
            unit_cost=unit_cost,
            total_cost=total_cost,
            currency="USD",
            occurred_at=now,
            source_reference=source_request_id,
            metadata_payload={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                **(metadata or {}),
            },
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def log_messaging_cost(
        self,
        organization_id: uuid.UUID,
        messages_count: int,
        channel: str = "WHATSAPP",
        cost_usd: Optional[Decimal] = None,
        source_reference: Optional[str] = None,
    ) -> CostEvent:
        """
        Logs direct cost incurred for sending or receiving customer messages.
        """
        now = datetime.now(timezone.utc)
        unit_rate = DEFAULT_COST_BENCHMARKS.get("whatsapp-marketing-out", Decimal("0.01"))
        total = cost_usd if cost_usd is not None else (Decimal(messages_count) * unit_rate)

        event = CostEvent(
            organization_id=organization_id,
            service="WHATSAPP" if channel.upper() == "WHATSAPP" else "MESSAGING",
            vendor="META" if channel.upper() == "WHATSAPP" else "VENDOR",
            unit="MESSAGES",
            quantity=Decimal(messages_count),
            unit_cost=unit_rate,
            total_cost=total,
            currency="USD",
            occurred_at=now,
            source_reference=source_reference,
            metadata_payload={"channel": channel},
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def log_payment_fee(
        self,
        organization_id: uuid.UUID,
        fee_amount: Decimal,
        currency: str = "INR",
        provider: str = "RAZORPAY",
        source_payment_id: Optional[str] = None,
    ) -> CostEvent:
        """
        Logs gateway processing fee incurred on a customer payment.
        """
        now = datetime.now(timezone.utc)
        event = CostEvent(
            organization_id=organization_id,
            service="PAYMENT_FEES",
            vendor=provider.upper(),
            unit="TRANSACTION",
            quantity=Decimal("1.0"),
            unit_cost=fee_amount,
            total_cost=fee_amount,
            currency=currency.upper(),
            occurred_at=now,
            source_reference=source_payment_id,
            metadata_payload={"provider": provider},
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event
