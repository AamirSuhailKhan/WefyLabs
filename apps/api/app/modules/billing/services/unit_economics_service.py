"""
WefyLabs Canonical Unit Economics & Financial Intelligence Service
==================================================================
Computes exact per-tenant financial metrics with complete provenance:
- MRR / ARR
- Gross & Net Revenue
- Payment fees, AI costs, WhatsApp messaging costs, storage costs
- Gross Profit & Gross Margin %
- Persists durable UnitEconomicsSnapshot and bridges with Build 09 UnitEconomicsRecord.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.billing_models import (
    Invoice as CanonicalInvoice,
    CostEvent,
    CreditLedgerEntry,
    CreditEntryType,
    UnitEconomicsSnapshot,
    Subscription as CanonicalSubscription,
    PlanVersion,
    PlanInterval,
    CanonicalInvoiceStatus,
)
from app.models.payment_models import PaymentRefund, RefundStatus
from app.modules.billing.domain.money import Money

logger = logging.getLogger("wefylabs.billing.unit_economics")

# Standard fixed reference conversion rate for reporting
USD_TO_INR_RATE = Decimal("83.50")


class UnitEconomicsService:
    """
    Computes and audits unit economics for organizations.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def compute_snapshot(
        self,
        organization_id: uuid.UUID,
        period_start: datetime,
        period_end: datetime,
        reporting_currency: str = "INR"
    ) -> UnitEconomicsSnapshot:
        """
        Computes financial snapshot for an organization within a time window.
        """
        currency = reporting_currency.upper()

        # 1. Gross Revenue (invoices paid in this window)
        stmt_inv = select(func.coalesce(func.sum(CanonicalInvoice.amount_paid), Decimal("0.0"))).where(
            and_(
                CanonicalInvoice.organization_id == organization_id,
                CanonicalInvoice.paid_at >= period_start,
                CanonicalInvoice.paid_at < period_end,
            )
        )
        gross_revenue = (await self.db.execute(stmt_inv)).scalar() or Decimal("0.0")

        # 2. Refunds in this window
        org_str = str(organization_id)
        stmt_ref = select(func.coalesce(func.sum(PaymentRefund.amount), 0)).where(
            and_(
                PaymentRefund.organization_id == org_str,
                PaymentRefund.status == RefundStatus.REFUNDED.value,
                PaymentRefund.created_at >= period_start,
                PaymentRefund.created_at < period_end,
            )
        )
        refunds_paise = (await self.db.execute(stmt_ref)).scalar() or 0
        refunds = Decimal(refunds_paise) / Decimal("100.0")  # Convert paise to INR

        # 3. Credits applied in this window
        stmt_cred = select(func.coalesce(func.sum(CreditLedgerEntry.amount), Decimal("0.0"))).where(
            and_(
                CreditLedgerEntry.organization_id == organization_id,
                CreditLedgerEntry.entry_type == CreditEntryType.CREDIT_APPLIED.value,
                CreditLedgerEntry.created_at >= period_start,
                CreditLedgerEntry.created_at < period_end,
            )
        )
        credits_applied = (await self.db.execute(stmt_cred)).scalar() or Decimal("0.0")

        net_revenue = max(Decimal("0.0"), gross_revenue - refunds - credits_applied)

        # 4. Variable Costs from CostEvent ledger
        stmt_costs = (
            select(
                CostEvent.service,
                CostEvent.currency,
                func.sum(CostEvent.total_cost).label("service_cost")
            )
            .where(
                and_(
                    CostEvent.organization_id == organization_id,
                    CostEvent.occurred_at >= period_start,
                    CostEvent.occurred_at < period_end,
                )
            )
            .group_by(CostEvent.service, CostEvent.currency)
        )
        cost_rows = (await self.db.execute(stmt_costs)).all()

        ai_cost = Decimal("0.0")
        messaging_cost = Decimal("0.0")
        payment_fees = Decimal("0.0")
        storage_cost = Decimal("0.0")
        other_cost = Decimal("0.0")

        for r in cost_rows:
            raw_c = Decimal(str(r.service_cost or 0))
            # Convert USD to INR if reporting in INR
            converted_cost = raw_c * USD_TO_INR_RATE if r.currency == "USD" and currency == "INR" else raw_c

            if r.service == "AI":
                ai_cost += converted_cost
            elif r.service in ("WHATSAPP", "MESSAGING"):
                messaging_cost += converted_cost
            elif r.service == "PAYMENT_FEES":
                payment_fees += converted_cost
            elif r.service == "STORAGE":
                storage_cost += converted_cost
            else:
                other_cost += converted_cost

        total_variable_cost = ai_cost + messaging_cost + payment_fees + storage_cost + other_cost
        gross_profit = net_revenue - total_variable_cost

        gross_margin_pct = Decimal("0.0")
        if net_revenue > Decimal("0.0"):
            gross_margin_pct = ((gross_profit / net_revenue) * Decimal("100.0")).quantize(Decimal("0.01"))

        # 5. MRR / ARR from Active Subscription
        stmt_sub = (
            select(CanonicalSubscription)
            .where(CanonicalSubscription.organization_id == organization_id)
            .options(selectinload(CanonicalSubscription.plan_version))
            .order_by(CanonicalSubscription.created_at.desc())
        )
        active_sub = (await self.db.execute(stmt_sub)).scalars().first()

        mrr = Decimal("0.0")
        if active_sub and active_sub.plan_version:
            plan_price = active_sub.plan_version.price
            if active_sub.plan_version.interval == PlanInterval.ANNUAL.value:
                mrr = (plan_price / Decimal("12.0")).quantize(Decimal("0.01"))
            else:
                mrr = plan_price

        arr = (mrr * Decimal("12.0")).quantize(Decimal("0.01"))

        snapshot = UnitEconomicsSnapshot(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
            currency=currency,
            mrr=mrr,
            arr=arr,
            gross_revenue=gross_revenue,
            net_revenue=net_revenue,
            refunds=refunds,
            credits=credits_applied,
            payment_fees=payment_fees,
            ai_cost=ai_cost,
            messaging_cost=messaging_cost,
            storage_cost=storage_cost,
            other_cost=other_cost,
            total_variable_cost=total_variable_cost,
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin_pct,
            data_quality_notes={
                "usd_to_inr_exchange_rate": str(USD_TO_INR_RATE),
                "source": "canonical_billing_and_cost_ledger",
            }
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)

        logger.info(
            f"[UnitEconomics] Org {organization_id}: NetRev={net_revenue}, Costs={total_variable_cost}, "
            f"GrossProfit={gross_profit} ({gross_margin_pct}%), MRR={mrr}"
        )
        return snapshot
