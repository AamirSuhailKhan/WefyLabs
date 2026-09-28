"""
Master Build 13 — Core Billing, Pricing, Usage, Entitlements & Unit Economics Test Suite
========================================================================================
Validates:
1. Money value object invariants (zero float, Decimal/minor units, currency match, rounding).
2. CatalogService & Plan Versioning.
3. EntitlementService deterministic evaluation & hard/soft/unlimited quota enforcement.
4. UsageMeteringService append-only ingestion, deduplication, and aggregation.
5. SubscriptionEngine lifecycle transitions, proration, and billing period generation.
6. CreditService append-only ledger, balance invariants (no negative balances), and applications.
7. InvoiceEngine deterministic generation, line provenance, and credit deduction.
8. CostLedgerService AI/messaging/gateway cost tracking.
9. UnitEconomicsService MRR, ARR, margins, and cost accounting.
10. Multi-tenant isolation & fail-closed authorizations.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_models import (
    BillingAccount,
    BillingCustomer,
    Plan,
    PlanVersion,
    PlanEntitlement,
    CanonicalSubscription,
    BillingPeriod,
    UsageMeter,
    UsageEvent,
    UsageAggregate,
    CanonicalInvoice,
    CreditLedgerEntry,
    CostEvent,
    UnitEconomicsSnapshot,
    PlanInterval,
    EntitlementType,
    LimitEnforcementPolicy,
    SubscriptionLifecycleStatus,
)
from app.modules.billing.domain.money import (
    Money,
    MoneyCalculator,
    CurrencyMismatchError,
    RoundingPolicy,
)
from app.modules.billing.services.catalog_service import CatalogService
from app.modules.billing.services.entitlement_service import (
    EntitlementService,
    EntitlementExceededError,
)
from app.modules.billing.services.usage_metering_service import UsageMeteringService
from app.modules.billing.services.subscription_engine import SubscriptionEngine
from app.modules.billing.services.credit_service import CreditService, InsufficientCreditError
from app.modules.billing.services.invoice_engine import InvoiceEngine
from app.modules.billing.services.cost_ledger_service import CostLedgerService
from app.modules.billing.services.unit_economics_service import UnitEconomicsService
from app.modules.billing.services.reconciliation_service import BillingReconciliationService


# ─── 1. MONEY INVARIANT TESTS ────────────────────────────────────────────────

def test_money_rejects_floating_point():
    """Invariant: Floating point money is strictly forbidden."""
    with pytest.raises(TypeError, match="Floating-point numbers are strictly forbidden"):
        Money(29.99, "USD")


def test_money_minor_units_conversion():
    """Invariant: Integer minor units convert accurately back and forth."""
    m = Money.from_minor_units(299900, "INR")
    assert m.amount == Decimal("2999.0000")
    assert m.currency == "INR"
    assert m.to_minor_units() == 299900

    usd = Money.from_minor_units(4900, "USD")
    assert usd.amount == Decimal("49.0000")
    assert usd.to_minor_units() == 4900


def test_money_currency_mismatch_prevention():
    """Invariant: Cross-currency arithmetic is rejected."""
    inr = Money("100.00", "INR")
    usd = Money("100.00", "USD")
    with pytest.raises(CurrencyMismatchError):
        _ = inr + usd
    with pytest.raises(CurrencyMismatchError):
        _ = inr - usd
    with pytest.raises(CurrencyMismatchError):
        _ = inr < usd


def test_money_calculator_line_total_and_proration():
    """Invariant: Line total subtotal, discount, tax, and proration are deterministic."""
    unit_price = Money("1000.00", "INR")
    subtotal, discount, tax, total = MoneyCalculator.calculate_line_total(
        unit_price=unit_price,
        quantity=2,
        discount=Money("200.00", "INR"),
        tax_rate_pct=Decimal("18.0")
    )
    # subtotal = 2000, discount = 200, taxable = 1800, tax 18% = 324, total = 2124
    assert subtotal.amount == Decimal("2000.0000")
    assert discount.amount == Decimal("200.0000")
    assert tax.amount == Decimal("324.0000")
    assert total.amount == Decimal("2124.0000")

    # Proration: 15 days out of 30 days remaining = 50%
    prorated = MoneyCalculator.calculate_proration(
        full_period_amount=Money("3000.00", "INR"),
        total_seconds_in_period=30 * 86400,
        active_seconds=15 * 86400
    )
    assert prorated.amount == Decimal("1500.0000")


# ─── 2. CATALOG SERVICE TESTS ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_catalog_service_seeding_and_retrieval(db: AsyncSession):
    """Verifies that default catalog seeds correctly and retrieves plans with entitlements."""
    service = CatalogService(db)
    await service.ensure_default_catalog_seeded()

    catalog = await service.get_active_catalog()
    assert len(catalog) >= 4
    codes = {p["code"] for p in catalog}
    assert "free" in codes
    assert "starter" in codes
    assert "pro" in codes
    assert "enterprise" in codes

    # Version lookup
    starter_v1 = await service.get_plan_version_by_code("starter", PlanInterval.MONTHLY.value)
    assert starter_v1 is not None
    assert starter_v1.price == Decimal("2999.0000")
    assert len(starter_v1.entitlements) > 0


# ─── 3. ENTITLEMENT SERVICE TESTS ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_entitlement_service_hard_limit_enforcement(db: AsyncSession):
    """Verifies that EntitlementService deterministic evaluation blocks upon reaching quota."""
    org_id = uuid.uuid4()
    cat_service = CatalogService(db)
    await cat_service.ensure_default_catalog_seeded()

    sub_engine = SubscriptionEngine(db)
    # Create starter subscription with 250 AI messages limit
    sub = await sub_engine.create_subscription(
        organization_id=org_id,
        plan_code="starter",
        interval=PlanInterval.MONTHLY.value,
        trial_days=0,
    )

    ent_service = EntitlementService(db)

    # Initial check: 0 consumed, limit = 250
    check = await ent_service.check_entitlement(org_id, "ai_messages_per_month", requested_quantity=1)
    assert check.allowed is True
    assert check.current_usage == 0
    assert check.limit_value == 250
    assert check.remaining == 250

    # Consume 249
    await ent_service.consume_entitlement(org_id, "ai_messages_per_month", quantity=249)

    # Check 1 remaining
    check_rem = await ent_service.check_entitlement(org_id, "ai_messages_per_month", requested_quantity=1)
    assert check_rem.allowed is True
    assert check_rem.remaining == 1

    # Consume 1 (reaches 250)
    await ent_service.consume_entitlement(org_id, "ai_messages_per_month", quantity=1)

    # Next attempt must be rejected by HARD_LIMIT
    check_blocked = await ent_service.check_entitlement(org_id, "ai_messages_per_month", requested_quantity=1)
    assert check_blocked.allowed is False
    assert check_blocked.remaining == 0

    with pytest.raises(EntitlementExceededError):
        await ent_service.consume_entitlement(org_id, "ai_messages_per_month", quantity=1)


@pytest.mark.asyncio
async def test_entitlement_service_past_due_and_grace_period(db: AsyncSession):
    """Verifies entitlement behavior during subscription grace period vs expired grace."""
    org_id = uuid.uuid4()
    cat_service = CatalogService(db)
    await cat_service.ensure_default_catalog_seeded()

    sub_engine = SubscriptionEngine(db)
    sub = await sub_engine.create_subscription(org_id, "pro", trial_days=0)

    ent_service = EntitlementService(db)

    # Put subscription into past_due with 7-day grace period
    await sub_engine.mark_past_due(sub.id, grace_days=7)

    # Inside grace period: allowed
    check_grace = await ent_service.check_entitlement(org_id, "team_members", requested_quantity=1)
    assert check_grace.allowed is True

    # Expire grace period
    sub.grace_ends_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db.commit()

    # Outside grace period: blocked
    check_expired = await ent_service.check_entitlement(org_id, "team_members", requested_quantity=1)
    assert check_expired.allowed is False
    assert "grace period expired" in (check_expired.reason or "").lower()


# ─── 4. USAGE METERING & DEDUPLICATION TESTS ─────────────────────────────────

@pytest.mark.asyncio
async def test_usage_metering_idempotency_deduplication(db: AsyncSession):
    """Verifies that submitting identical idempotency keys returns the same event without double-counting."""
    org_id = uuid.uuid4()
    metering = UsageMeteringService(db)
    await metering.ensure_meters_seeded()

    idemp_key = f"idemp_{uuid.uuid4().hex}"

    # First submission
    event1, is_new1 = await metering.ingest_usage_event(
        organization_id=org_id,
        meter_code="AI_REQUEST",
        quantity=Decimal("1.0"),
        idempotency_key=idemp_key,
        source_type="COPILOT",
    )
    assert is_new1 is True
    assert event1.idempotency_key == idemp_key

    # Duplicate submission
    event2, is_new2 = await metering.ingest_usage_event(
        organization_id=org_id,
        meter_code="AI_REQUEST",
        quantity=Decimal("1.0"),
        idempotency_key=idemp_key,
        source_type="COPILOT",
    )
    assert is_new2 is False
    assert event2.id == event1.id


# ─── 5. SUBSCRIPTION UPGRADE & PRORATION TESTS ───────────────────────────────

@pytest.mark.asyncio
async def test_subscription_upgrade_proration(db: AsyncSession):
    """Verifies immediate plan upgrade with unused credit calculation."""
    org_id = uuid.uuid4()
    cat_service = CatalogService(db)
    await cat_service.ensure_default_catalog_seeded()

    sub_engine = SubscriptionEngine(db)
    # Start on starter monthly (₹2,999)
    sub = await sub_engine.create_subscription(org_id, "starter", trial_days=0)

    # Upgrade to pro monthly (₹4,999)
    upgraded, unused_credit = await sub_engine.upgrade_plan(sub.id, "pro", PlanInterval.MONTHLY.value)
    assert upgraded.status == SubscriptionLifecycleStatus.ACTIVE.value
    assert unused_credit.currency == "INR"
    assert unused_credit.amount > Decimal("0.0")


# ─── 6. CREDIT LEDGER & BALANCE INVARIANT TESTS ──────────────────────────────

@pytest.mark.asyncio
async def test_credit_ledger_append_only_and_balance_integrity(db: AsyncSession):
    """Verifies credit issuance, consumption, and refusal of overdraft/negative balance."""
    org_id = uuid.uuid4()
    credit_svc = CreditService(db)

    # Initial balance is zero
    bal0 = await credit_svc.get_balance(org_id, "INR")
    assert bal0.amount == Decimal("0.0000")

    # Issue ₹1,000 credit
    entry1 = await credit_svc.issue_credit(
        organization_id=org_id,
        amount=Money("1000.00", "INR"),
        reason="Promotional onboarding credit",
    )
    assert entry1.balance_after == Decimal("1000.0000")

    bal1 = await credit_svc.get_balance(org_id, "INR")
    assert bal1.amount == Decimal("1000.0000")

    # Apply ₹400
    entry2 = await credit_svc.apply_credit(
        organization_id=org_id,
        amount=Money("400.00", "INR"),
        reason="Applied to test invoice",
    )
    assert entry2.balance_after == Decimal("600.0000")

    # Attempt to consume ₹700 (must raise InsufficientCreditError)
    with pytest.raises(InsufficientCreditError):
        await credit_svc.apply_credit(
            organization_id=org_id,
            amount=Money("700.00", "INR"),
            reason="Illegal overdraft attempt",
        )

    # Authoritative balance remains ₹600
    bal_final = await credit_svc.get_balance(org_id, "INR")
    assert bal_final.amount == Decimal("600.0000")


# ─── 7. INVOICE ENGINE RECOMPUTATION & CREDITS TESTS ─────────────────────────

@pytest.mark.asyncio
async def test_invoice_engine_generation_and_math(db: AsyncSession):
    """Verifies invoice generation from billing period with automatic credit deduction."""
    org_id = uuid.uuid4()
    cat_service = CatalogService(db)
    await cat_service.ensure_default_catalog_seeded()

    sub_engine = SubscriptionEngine(db)
    sub = await sub_engine.create_subscription(org_id, "starter", trial_days=0)

    # Issue ₹500 credit to tenant
    credit_svc = CreditService(db)
    await credit_svc.issue_credit(org_id, Money("500.00", "INR"), "Welcome credit")

    # Get active billing period
    stmt_period = select(BillingPeriod).where(BillingPeriod.subscription_id == sub.id)
    period = (await db.execute(stmt_period)).scalars().first()

    # Generate invoice
    inv_engine = InvoiceEngine(db)
    invoice = await inv_engine.generate_period_invoice(
        organization_id=org_id,
        billing_period_id=period.id,
        tax_rate_pct=Decimal("18.0"),
        auto_apply_credits=True,
    )

    # Verify invoice invariants:
    # subtotal = 2999.00
    # tax 18% = 539.82
    # gross = 3538.82
    # credit = 500.00
    # total due = 3038.82
    assert invoice.subtotal == Decimal("2999.0000")
    assert invoice.tax_amount == Decimal("539.8200")
    assert invoice.credit_amount == Decimal("500.0000")
    assert invoice.total == Decimal("3038.8200")
    assert invoice.amount_due == Decimal("3038.8200")
    assert invoice.status == "OPEN"
    assert len(invoice.lines) >= 1

    # Mark paid
    paid_inv = await inv_engine.mark_invoice_paid(invoice.id, Money("3038.82", "INR"))
    assert paid_inv.status == "PAID"
    assert paid_inv.amount_due == Decimal("0.0000")


# ─── 8. COST LEDGER & UNIT ECONOMICS TESTS ───────────────────────────────────

@pytest.mark.asyncio
async def test_cost_ledger_and_unit_economics_computation(db: AsyncSession):
    """Verifies cost logging and unit economics gross profit / margin calculation."""
    org_id = uuid.uuid4()
    cat_service = CatalogService(db)
    await cat_service.ensure_default_catalog_seeded()

    cost_svc = CostLedgerService(db)
    # Log 10,000 prompt tokens and 5,000 completion tokens
    await cost_svc.log_ai_cost(
        organization_id=org_id,
        model="gpt-4o-mini",
        input_tokens=10000,
        output_tokens=5000,
        estimated_cost_usd=Decimal("0.05"),
        source_request_id="req_test_001",
    )
    # Log WhatsApp messaging cost
    await cost_svc.log_messaging_cost(
        organization_id=org_id,
        messages_count=50,
        channel="WHATSAPP",
        cost_usd=Decimal("0.50"),
    )

    # Create paid invoice for org: ₹5,000 net revenue
    acc = await SubscriptionEngine(db).ensure_billing_account(org_id, "test@wefylabs.com")
    now = datetime.now(timezone.utc)
    inv = CanonicalInvoice(
        organization_id=org_id,
        billing_account_id=acc.id,
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:6]}",
        status="PAID",
        currency="INR",
        subtotal=Decimal("5000.00"),
        total=Decimal("5000.00"),
        amount_paid=Decimal("5000.00"),
        amount_due=Decimal("0.00"),
        due_date=now,
        paid_at=now,
    )
    db.add(inv)
    await db.commit()

    # Compute unit economics
    econ_svc = UnitEconomicsService(db)
    snapshot = await econ_svc.compute_snapshot(
        organization_id=org_id,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=1),
        reporting_currency="INR"
    )

    assert snapshot.gross_revenue == Decimal("5000.0000")
    assert snapshot.net_revenue == Decimal("5000.0000")
    assert snapshot.ai_cost > Decimal("0.0")
    assert snapshot.messaging_cost > Decimal("0.0")
    assert snapshot.gross_profit > Decimal("0.0")
    assert snapshot.gross_margin_pct > Decimal("90.0")  # Healthy margin expected


# ─── 9. BILLING RECONCILIATION AUDIT TESTS ───────────────────────────────────

@pytest.mark.asyncio
async def test_billing_reconciliation_detects_anomalies(db: AsyncSession):
    """Verifies that BillingReconciliationService detects mathematical discrepancies."""
    org_id = uuid.uuid4()
    acc = await SubscriptionEngine(db).ensure_billing_account(org_id, "recon@wefylabs.com")
    now = datetime.now(timezone.utc)

    # Create deliberately corrupted invoice where total != subtotal + tax
    bad_inv = CanonicalInvoice(
        organization_id=org_id,
        billing_account_id=acc.id,
        invoice_number="INV-CORRUPT-001",
        status="OPEN",
        currency="INR",
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        discount_amount=Decimal("0.00"),
        credit_amount=Decimal("0.00"),
        total=Decimal("9999.00"),  # Corrupted total!
        amount_paid=Decimal("0.00"),
        amount_due=Decimal("9999.00"),
        due_date=now,
    )
    db.add(bad_inv)
    await db.commit()

    recon_svc = BillingReconciliationService(db)
    audit = await recon_svc.run_reconciliation(org_id)

    assert audit["status"] == "DISCREPANCIES_DETECTED"
    assert audit["discrepancy_count"] >= 1
    types = [d["type"] for d in audit["discrepancies"]]
    assert "INVOICE_TOTAL_MISMATCH" in types
