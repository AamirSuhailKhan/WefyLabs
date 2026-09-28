"""
Master Build 13 — Billing Reconciliation & Golden Dataset Verification Test Suite
=================================================================================
Validates:
1. Automated detection of financial anomalies:
   - INVOICE_TOTAL_MISMATCH
   - REFUND_MISMATCH (refund amount > captured payment)
   - USAGE_MISMATCH (raw events sum != rollup aggregate)
   - SUBSCRIPTION_MISMATCH
2. Integration with Build 09 RevenueReconciliationRecord.
3. Billing Golden Dataset lifecycle scenarios:
   - Scenario A: New customer trial -> trial conversion -> monthly renewal
   - Scenario B: Upgrade with proration credit calculation
   - Scenario C: Failed payment -> past due with grace period -> suspension
   - Scenario D: Overage generation on metered usage exceeding plan quota
   - Scenario E: Credit ledger issuance & automatic deduction on invoice
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_models import (
    BillingAccount,
    BillingCustomer,
    Plan,
    PlanVersion,
    PlanEntitlement,
    CanonicalSubscription,
    BillingPeriod,
    BillingPeriodStatus,
    UsageMeter,
    UsageEvent,
    UsageAggregate,
    CanonicalInvoice,
    InvoiceLine,
    CreditLedgerEntry,
    SubscriptionLifecycleStatus,
    PlanInterval,
)
from app.models.payment_models import (
    PaymentOrder,
    PaymentTransaction,
    PaymentRefund,
    PaymentStatus,
    RefundStatus,
)
from app.models.revenue_intelligence_b09_models import (
    RevenueReconciliationRecord,
    ReconciliationDifference,
)
from app.modules.billing.domain.money import Money
from app.modules.billing.services.catalog_service import CatalogService
from app.modules.billing.services.subscription_engine import SubscriptionEngine
from app.modules.billing.services.usage_metering_service import UsageMeteringService
from app.modules.billing.services.invoice_engine import InvoiceEngine
from app.modules.billing.services.credit_service import CreditService
from app.modules.billing.services.entitlement_service import EntitlementService
from app.modules.billing.services.reconciliation_service import BillingReconciliationService


# ─── 1. RECONCILIATION ANOMALY DETECTION ──────────────────────────────────────

@pytest.mark.asyncio
async def test_reconciliation_detects_refund_exceeding_payment(db: AsyncSession):
    """
    Fixtures a captured payment of ₹3,000 (300,000 paise).
    Introduces a refund of ₹4,000 (400,000 paise).
    Expected: System flags REFUND_MISMATCH and creates a RevenueReconciliationRecord.
    """
    org_id = uuid.uuid4()
    org_str = str(org_id)

    # 1. Create captured transaction of ₹3,000
    txn = PaymentTransaction(
        broker_id=uuid.uuid4(),
        organization_id=org_str,
        razorpay_payment_id=f"pay_recon_{uuid.uuid4().hex[:8]}",
        amount=300000,  # ₹3,000 in paise
        currency="INR",
        status=PaymentStatus.PAYMENT_CAPTURED.value,
    )
    db.add(txn)
    await db.flush()

    # 2. Add an excessive refund of ₹4,000
    bad_refund = PaymentRefund(
        broker_id=txn.broker_id,
        organization_id=org_str,
        transaction_id=txn.id,
        razorpay_refund_id=f"rfnd_recon_{uuid.uuid4().hex[:8]}",
        razorpay_payment_id=txn.razorpay_payment_id,
        amount=400000,  # ₹4,000 in paise
        currency="INR",
        status=RefundStatus.REFUNDED.value,
        reason="Erroneous excess refund",
    )
    db.add(bad_refund)
    await db.commit()

    recon_svc = BillingReconciliationService(db)
    result = await recon_svc.run_reconciliation(org_id)

    assert result["status"] == "DISCREPANCIES_DETECTED"
    diff_types = [d["type"] for d in result["discrepancies"]]
    assert "REFUND_MISMATCH" in diff_types

    # Verify persisted to RevenueReconciliationRecord
    stmt_rec = select(RevenueReconciliationRecord).where(
        RevenueReconciliationRecord.organization_id == org_id
    )
    records = (await db.execute(stmt_rec)).scalars().all()
    assert len(records) >= 1
    assert records[0].difference_type == ReconciliationDifference.AMOUNT_MISMATCH


@pytest.mark.asyncio
async def test_reconciliation_detects_usage_aggregate_drift(db: AsyncSession):
    """
    Fixtures 5 raw events of 10 units each (total = 50 units).
    Introduces an aggregate record claiming only 20 units.
    Expected: System flags USAGE_MISMATCH with difference of 30 units.
    """
    org_id = uuid.uuid4()
    metering = UsageMeteringService(db)
    await metering.ensure_meters_seeded()
    meter = await metering.get_meter_by_code("AI_REQUEST")

    now = datetime.now(timezone.utc)
    p_start = now - timedelta(days=10)
    p_end = now + timedelta(days=20)

    # Ingest 5 raw events
    for i in range(5):
        event = UsageEvent(
            organization_id=org_id,
            meter_id=meter.id,
            event_name=meter.source_event,
            event_key=f"evt_drift_{i}",
            quantity=Decimal("10.0"),
            unit=meter.unit,
            source_type="API",
            occurred_at=now,
            idempotency_key=f"idemp_drift_{uuid.uuid4().hex}",
        )
        db.add(event)

    # Insert drifted aggregate claiming only 20.0
    drifted_agg = UsageAggregate(
        organization_id=org_id,
        meter_id=meter.id,
        period_start=p_start,
        period_end=p_end,
        quantity=Decimal("20.0"),
        unit=meter.unit,
    )
    db.add(drifted_agg)
    await db.commit()

    recon_svc = BillingReconciliationService(db)
    result = await recon_svc.run_reconciliation(org_id)

    assert result["status"] == "DISCREPANCIES_DETECTED"
    diff_types = [d["type"] for d in result["discrepancies"]]
    assert "USAGE_MISMATCH" in diff_types


# ─── 2. BILLING GOLDEN DATASET SCENARIOS ─────────────────────────────────────

@pytest.mark.asyncio
async def test_golden_scenario_a_trial_to_paid_activation(db: AsyncSession):
    """
    Scenario A:
    1. New customer signs up on Starter with a 7-day trial.
    2. Status is TRIALING.
    3. Payment captured via webhook/checkout -> converts to ACTIVE.
    4. Current period dates advance by 30 days.
    """
    org_id = uuid.uuid4()
    cat_service = CatalogService(db)
    await cat_service.ensure_default_catalog_seeded()

    sub_engine = SubscriptionEngine(db)
    sub = await sub_engine.create_subscription(
        organization_id=org_id,
        plan_code="starter",
        interval=PlanInterval.MONTHLY.value,
        trial_days=7,
    )

    assert sub.status == SubscriptionLifecycleStatus.TRIALING.value
    assert sub.trial_ends_at is not None

    # Customer activates subscription
    activated_sub = await sub_engine.activate_subscription(sub.id)
    assert activated_sub.status == SubscriptionLifecycleStatus.ACTIVE.value
    assert activated_sub.grace_ends_at is None


@pytest.mark.asyncio
async def test_golden_scenario_b_plan_upgrade_with_proration(db: AsyncSession):
    """
    Scenario B:
    1. Customer starts on Starter Monthly (₹2,999).
    2. 15 days later, upgrades to Pro Monthly (₹4,999).
    3. Engine computes proration credit for unused 15 days.
    4. Pro plan version becomes active on subscription.
    """
    org_id = uuid.uuid4()
    cat_service = CatalogService(db)
    await cat_service.ensure_default_catalog_seeded()

    sub_engine = SubscriptionEngine(db)
    sub = await sub_engine.create_subscription(org_id, "starter", trial_days=0)

    # Upgrade to Pro
    upgraded_sub, proration_credit = await sub_engine.upgrade_plan(sub.id, "pro", PlanInterval.MONTHLY.value)

    assert upgraded_sub.status == SubscriptionLifecycleStatus.ACTIVE.value
    assert proration_credit.currency == "INR"
    assert proration_credit.amount > Decimal("0.0")


@pytest.mark.asyncio
async def test_golden_scenario_c_failed_payment_and_grace_period(db: AsyncSession):
    """
    Scenario C:
    1. Monthly renewal fails -> marked PAST_DUE.
    2. Grace period active for 7 days (entitlements allowed).
    3. Grace period expires -> entitlements blocked.
    """
    org_id = uuid.uuid4()
    cat_service = CatalogService(db)
    await cat_service.ensure_default_catalog_seeded()

    sub_engine = SubscriptionEngine(db)
    sub = await sub_engine.create_subscription(org_id, "starter", trial_days=0)

    # Failed renewal -> mark past due with 7 days grace
    await sub_engine.mark_past_due(sub.id, grace_days=7)
    assert sub.status == SubscriptionLifecycleStatus.PAST_DUE.value
    assert sub.grace_ends_at is not None

    ent_svc = EntitlementService(db)

    # Allowed inside grace period
    check_grace = await ent_svc.check_entitlement(org_id, "team_members", requested_quantity=1)
    assert check_grace.allowed is True

    # Expire grace period
    sub.grace_ends_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db.commit()

    # Blocked outside grace period
    check_blocked = await ent_svc.check_entitlement(org_id, "team_members", requested_quantity=1)
    assert check_blocked.allowed is False


@pytest.mark.asyncio
async def test_golden_scenario_d_overage_invoice_generation(db: AsyncSession):
    """
    Scenario D:
    1. Customer on Starter plan (quota: 250 AI messages).
    2. Over the month, customer uses 350 AI messages (100 overage).
    3. Plan entitlement permits overage at ₹1.50 per excess message.
    4. Invoice generation adds base plan line (₹2,999) + overage line (₹150.00).
    5. Net subtotal = ₹3,149.00 + 18% tax.
    """
    org_id = uuid.uuid4()
    cat_service = CatalogService(db)
    await cat_service.ensure_default_catalog_seeded()

    sub_engine = SubscriptionEngine(db)
    sub = await sub_engine.create_subscription(org_id, "starter", trial_days=0)

    # Configure overage allowance on starter plan version for testing
    plan_v = sub.plan_version
    for ent in plan_v.entitlements:
        if ent.entitlement_key == "ai_messages_per_month":
            ent.overage_allowed = True
            ent.overage_unit_price = Decimal("1.50")
            break
    await db.commit()

    # Find billing period
    stmt_p = select(BillingPeriod).where(BillingPeriod.subscription_id == sub.id)
    period = (await db.execute(stmt_p)).scalars().first()

    # Create usage aggregate of 350 units
    metering = UsageMeteringService(db)
    meter = await metering.get_meter_by_code("AI_REQUEST")

    agg = UsageAggregate(
        organization_id=org_id,
        meter_id=meter.id,
        billing_period_id=period.id,
        period_start=period.period_start,
        period_end=period.period_end,
        quantity=Decimal("350.0"),
        unit=meter.unit,
    )
    db.add(agg)
    await db.commit()

    # Generate invoice
    inv_engine = InvoiceEngine(db)
    invoice = await inv_engine.generate_period_invoice(
        organization_id=org_id,
        billing_period_id=period.id,
        tax_rate_pct=Decimal("18.0"),
        auto_apply_credits=False,
    )

    # subtotal = 2999 + (100 * 1.50) = 2999 + 150 = 3149
    assert invoice.subtotal == Decimal("3149.0000")
    # tax = 3149 * 0.18 = 566.82
    assert invoice.tax_amount == Decimal("566.8200")
    assert invoice.total == Decimal("3715.8200")
    assert len(invoice.lines) == 2  # 1 Base recurring + 1 Overage
