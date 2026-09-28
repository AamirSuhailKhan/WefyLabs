"""
WefyLabs Canonical Invoice Engine
=================================
Automated invoice generation from billing periods, recurring plan items,
usage aggregates, taxes, discounts, and credit ledger applications.
Invariants:
- All monetary math uses Money and MoneyCalculator (zero float).
- Invoices are fully recomputable from their lines and applied credits.
- Invoice number is unique and monotonic per organization.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.billing_models import (
    Invoice as CanonicalInvoice,
    InvoiceLine,
    BillingPeriod,
    BillingPeriodStatus,
    Subscription as CanonicalSubscription,
    PlanVersion,
    PlanEntitlement,
    UsageAggregate,
    UsageMeter,
    CanonicalInvoiceStatus,
)
from app.modules.billing.domain.money import Money, MoneyCalculator
from app.modules.billing.services.credit_service import CreditService

logger = logging.getLogger("wefylabs.billing.invoice")


class InvoiceEngine:
    """
    Deterministic invoice generation and lifecycle management.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.credit_service = CreditService(db)

    async def _generate_invoice_number(self, organization_id: uuid.UUID) -> str:
        """
        Generates sequential invoice number: INV-{YEAR}-{MONTH}-{SHORT_ORG}-{SEQ}
        """
        now = datetime.now(timezone.utc)
        year_str = now.strftime("%Y")
        month_str = now.strftime("%m")
        org_prefix = str(organization_id)[:6].upper()

        stmt = select(func.count(CanonicalInvoice.id)).where(CanonicalInvoice.organization_id == organization_id)
        count = (await self.db.execute(stmt)).scalar() or 0
        seq = count + 1
        return f"INV-{year_str}{month_str}-{org_prefix}-{seq:04d}"

    async def generate_period_invoice(
        self,
        organization_id: uuid.UUID,
        billing_period_id: uuid.UUID,
        tax_rate_pct: Decimal = Decimal("18.0"),  # Default 18% GST for INR
        auto_apply_credits: bool = True,
    ) -> CanonicalInvoice:
        """
        Generates an authoritative invoice for a closed or closing billing period.
        """
        # Check if invoice already exists for this billing period
        stmt_exist = select(CanonicalInvoice).where(
            and_(
                CanonicalInvoice.organization_id == organization_id,
                CanonicalInvoice.billing_period_id == billing_period_id,
            )
        )
        existing = (await self.db.execute(stmt_exist)).scalars().first()
        if existing:
            logger.info(f"[InvoiceEngine] Invoice already exists for period {billing_period_id}: {existing.invoice_number}")
            return existing

        stmt_period = (
            select(BillingPeriod)
            .where(BillingPeriod.id == billing_period_id)
            .options(
                selectinload(BillingPeriod.subscription).selectinload(CanonicalSubscription.plan_version).selectinload(PlanVersion.entitlements)
            )
        )
        period = (await self.db.execute(stmt_period)).scalars().first()
        if not period:
            raise ValueError(f"Billing period {billing_period_id} not found.")

        subscription = period.subscription
        if not subscription or not subscription.plan_version:
            raise ValueError(f"Subscription or plan version missing for billing period {billing_period_id}.")

        plan_version = subscription.plan_version
        currency = plan_version.currency
        lines: List[InvoiceLine] = []

        # 1. Base Plan Subscription Recurring Line Item
        plan_base_price = Money(plan_version.price, currency)
        subtotal_acc = plan_base_price
        discount_acc = Money(Decimal("0.0"), currency)

        base_line = InvoiceLine(
            description=f"Subscription: Plan {plan_version.plan_id} ({plan_version.interval})",
            quantity=Decimal("1.0"),
            unit_price=plan_base_price.amount,
            subtotal=plan_base_price.amount,
            discount=Decimal("0.0"),
            tax_amount=Decimal("0.0"),
            total=plan_base_price.amount,
            currency=currency,
            plan_version_id=plan_version.id,
            source_type="PLAN_RECURRING",
            source_id=str(subscription.id),
        )
        lines.append(base_line)

        # 2. Usage Overage Line Items
        stmt_agg = (
            select(UsageAggregate)
            .where(
                and_(
                    UsageAggregate.organization_id == organization_id,
                    UsageAggregate.billing_period_id == billing_period_id,
                )
            )
        )
        aggregates = (await self.db.execute(stmt_agg)).scalars().all()

        METER_TO_ENTITLEMENT_MAP = {
            "AI_REQUEST": ["ai_messages_per_month", "ai_request", "ai_agent.request"],
            "WHATSAPP_MESSAGE": ["whatsapp_messages_per_month", "whatsapp_message", "communication.whatsapp_message"],
            "DOCUMENT_PROCESSED": ["document_processing", "document_processed"],
            "WORKFLOW_EXECUTION": ["workflow_executions", "workflow_execution"],
        }

        for agg in aggregates:
            # Check if plan entitlement permits overage and what the rate is
            stmt_meter = select(UsageMeter).where(UsageMeter.id == agg.meter_id)
            meter = (await self.db.execute(stmt_meter)).scalars().first()
            if not meter:
                continue

            ent_keys = {meter.source_event, meter.code.lower(), *METER_TO_ENTITLEMENT_MAP.get(meter.code, [])}
            matching_ent = next(
                (e for e in plan_version.entitlements if e.entitlement_key in ent_keys),
                None
            )
            if matching_ent and matching_ent.overage_allowed and matching_ent.limit_value is not None:
                limit_dec = Decimal(matching_ent.limit_value)
                if agg.quantity > limit_dec:
                    overage_qty = agg.quantity - limit_dec
                    unit_rate = Money(matching_ent.overage_unit_price or Decimal("1.0"), currency)
                    overage_line_subtotal = (unit_rate * overage_qty).round()

                    ov_line = InvoiceLine(
                        description=f"Overage: {meter.name} ({overage_qty} {meter.unit} beyond included {matching_ent.limit_value})",
                        quantity=overage_qty,
                        unit_price=unit_rate.amount,
                        subtotal=overage_line_subtotal.amount,
                        discount=Decimal("0.0"),
                        tax_amount=Decimal("0.0"),
                        total=overage_line_subtotal.amount,
                        currency=currency,
                        meter_id=meter.id,
                        source_type="METER_OVERAGE",
                        source_id=str(agg.id),
                    )
                    lines.append(ov_line)
                    subtotal_acc = subtotal_acc + overage_line_subtotal

        # 3. Calculate Tax
        tax_factor = tax_rate_pct / Decimal("100.0")
        tax_acc = (subtotal_acc * tax_factor).round()
        gross_total = subtotal_acc + tax_acc

        # 4. Check & Apply Credits
        applied_credits = Money(Decimal("0.0"), currency)
        if auto_apply_credits:
            available_credit = await self.credit_service.get_balance(organization_id, currency)
            if available_credit.is_positive():
                to_apply = min(available_credit, gross_total)
                if to_apply.is_positive():
                    applied_credits = to_apply

        net_total = gross_total - applied_credits
        invoice_number = await self._generate_invoice_number(organization_id)
        now = datetime.now(timezone.utc)

        status = CanonicalInvoiceStatus.PAID.value if net_total.is_zero() else CanonicalInvoiceStatus.OPEN.value
        paid_at = now if net_total.is_zero() else None

        invoice = CanonicalInvoice(
            organization_id=organization_id,
            billing_account_id=subscription.billing_account_id,
            subscription_id=subscription.id,
            billing_period_id=period.id,
            invoice_number=invoice_number,
            status=status,
            currency=currency,
            subtotal=subtotal_acc.amount,
            discount_amount=discount_acc.amount,
            tax_amount=tax_acc.amount,
            credit_amount=applied_credits.amount,
            total=net_total.amount,
            amount_paid=gross_total.amount if net_total.is_zero() else applied_credits.amount,
            amount_due=net_total.amount,
            due_date=now + timedelta(days=14),
            paid_at=paid_at,
        )
        self.db.add(invoice)
        await self.db.flush()

        for line in lines:
            line.invoice_id = invoice.id
            self.db.add(line)

        # Record credit consumption in ledger if credits were applied
        if applied_credits.is_positive():
            await self.credit_service.apply_credit(
                organization_id=organization_id,
                amount=applied_credits,
                invoice_id=invoice.id,
                reason=f"Applied automatically to invoice {invoice_number}"
            )

        period.status = BillingPeriodStatus.INVOICED.value
        await self.db.commit()
        await self.db.refresh(invoice)

        logger.info(f"[InvoiceEngine] Generated invoice {invoice.invoice_number} for org {organization_id}. Total: {net_total}")
        return invoice

    async def mark_invoice_paid(
        self,
        invoice_id: uuid.UUID,
        amount_paid: Money,
        paid_at: Optional[datetime] = None
    ) -> CanonicalInvoice:
        """
        Marks an invoice as paid (or partially paid) with payment provenance.
        """
        stmt = select(CanonicalInvoice).where(CanonicalInvoice.id == invoice_id)
        inv = (await self.db.execute(stmt)).scalars().first()
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found.")

        now = paid_at or datetime.now(timezone.utc)
        curr_due = Money(inv.amount_due, inv.currency)
        curr_paid = Money(inv.amount_paid, inv.currency)

        new_paid = curr_paid + amount_paid
        new_due = max(Money(Decimal("0.0"), inv.currency), curr_due - amount_paid)

        inv.amount_paid = new_paid.amount
        inv.amount_due = new_due.amount

        if new_due.is_zero():
            inv.status = CanonicalInvoiceStatus.PAID.value
            inv.paid_at = now
        else:
            inv.status = CanonicalInvoiceStatus.PARTIALLY_PAID.value

        await self.db.commit()
        await self.db.refresh(inv)
        return inv

    async def void_invoice(
        self,
        invoice_id: uuid.UUID,
        reason: str
    ) -> CanonicalInvoice:
        """
        Voids an open or unpaid invoice.
        """
        stmt = select(CanonicalInvoice).where(CanonicalInvoice.id == invoice_id)
        inv = (await self.db.execute(stmt)).scalars().first()
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found.")

        if inv.status == CanonicalInvoiceStatus.PAID.value:
            raise ValueError("Cannot void a fully paid invoice. Use refunds or credit notes.")

        inv.status = CanonicalInvoiceStatus.VOID.value
        inv.voided_at = datetime.now(timezone.utc)
        inv.notes = (inv.notes or "") + f" [Voided: {reason}]"

        await self.db.commit()
        await self.db.refresh(inv)
        return inv
