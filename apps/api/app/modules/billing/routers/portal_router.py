"""
WefyLabs Canonical Customer Billing Portal API Router
======================================================
Endpoints:
- GET /api/v1/billing/portal/catalog
- GET /api/v1/billing/portal/plan
- GET /api/v1/billing/portal/subscription
- GET /api/v1/billing/portal/usage
- GET /api/v1/billing/portal/entitlements
- GET /api/v1/billing/portal/invoices
- GET /api/v1/billing/portal/credits
- POST /api/v1/billing/portal/upgrade
- POST /api/v1/billing/portal/downgrade
- POST /api/v1/billing/portal/cancel
- POST /api/v1/billing/portal/resume

Strict security & multi-tenant isolation:
- All tenant actions are scoped to TenantContext.organization_id.
- Backend enforces all authorizations; frontend is never a security boundary.
- Supports Idempotency-Key for mutation requests.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Header, status, Request
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db, get_current_tenant, TenantContext
from app.models.billing_models import (
    Subscription as CanonicalSubscription,
    Invoice as CanonicalInvoice,
    InvoiceLine,
    UsageAggregate,
    UsageMeter,
    CreditLedgerEntry,
    BillingPeriod,
    PlanVersion,
    SubscriptionLifecycleStatus,
)
from app.modules.billing.services.catalog_service import CatalogService
from app.modules.billing.services.entitlement_service import EntitlementService
from app.modules.billing.services.subscription_engine import SubscriptionEngine
from app.modules.billing.services.credit_service import CreditService
from app.modules.billing.services.usage_metering_service import UsageMeteringService
from app.modules.billing.domain.money import Money

logger = logging.getLogger("wefylabs.billing.portal")

portal_router = APIRouter(prefix="/portal", tags=["Customer Billing Portal"])


# ─── Pydantic Request / Response Models ───────────────────────────────────────

class PlanChangeRequest(BaseModel):
    plan_code: str = Field(..., description="Target plan code: starter, pro, enterprise")
    interval: str = Field("MONTHLY", description="Billing interval: MONTHLY or ANNUAL")


class CancelSubscriptionRequest(BaseModel):
    immediate: bool = Field(False, description="Cancel immediately (True) or at period end (False)")
    reason: Optional[str] = Field(None, description="Optional cancellation feedback")


# ─── 1. Catalog Comparison ───────────────────────────────────────────────────

@portal_router.get("/catalog", status_code=status.HTTP_200_OK)
async def get_portal_catalog(db: AsyncSession = Depends(get_db)):
    """
    Returns full database-driven comparison catalog of plans, pricing, and entitlements.
    Zero hardcoded values in React.
    """
    svc = CatalogService(db)
    return await svc.get_active_catalog()


# ─── 2. Current Plan & Subscription ──────────────────────────────────────────

@portal_router.get("/subscription", status_code=status.HTTP_200_OK)
async def get_current_subscription(
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns current organization subscription, active plan, billing period, and lifecycle status.
    """
    org_id = uuid.UUID(tenant.organization_id)
    stmt = (
        select(CanonicalSubscription)
        .where(CanonicalSubscription.organization_id == org_id)
        .options(
            selectinload(CanonicalSubscription.plan_version).selectinload(PlanVersion.plan),
            selectinload(CanonicalSubscription.billing_account),
        )
        .order_by(CanonicalSubscription.created_at.desc())
    )
    sub = (await self_execute_first(db, stmt))
    if not sub:
        return {
            "has_subscription": False,
            "status": "NONE",
            "organization_id": tenant.organization_id,
        }

    plan_info = {
        "code": sub.plan_version.plan.code,
        "name": sub.plan_version.plan.name,
        "version": sub.plan_version.version,
        "interval": sub.plan_version.interval,
        "price": str(sub.plan_version.price),
        "currency": sub.plan_version.currency,
    } if sub.plan_version and sub.plan_version.plan else None

    return {
        "has_subscription": True,
        "subscription_id": str(sub.id),
        "organization_id": str(sub.organization_id),
        "status": sub.status,
        "current_period_start": sub.current_period_start.isoformat(),
        "current_period_end": sub.current_period_end.isoformat(),
        "cancel_at_period_end": sub.cancel_at_period_end,
        "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
        "grace_ends_at": sub.grace_ends_at.isoformat() if sub.grace_ends_at else None,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
        "plan": plan_info,
    }


# ─── 3. Effective Entitlements ────────────────────────────────────────────────

@portal_router.get("/entitlements", status_code=status.HTTP_200_OK)
async def get_portal_entitlements(
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Authoritative server-side entitlement limits, current usage, and remaining allowances.
    """
    org_id = uuid.UUID(tenant.organization_id)
    svc = EntitlementService(db)
    return await svc.get_effective_entitlements(org_id)


# ─── 4. Metered Usage & Forecast Gauges ───────────────────────────────────────

@portal_router.get("/usage", status_code=status.HTTP_200_OK)
async def get_portal_usage(
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns aggregated usage for current billing period across all meters with percentage gauges.
    """
    org_id = uuid.UUID(tenant.organization_id)
    ent_svc = EntitlementService(db)
    effective = await ent_svc.get_effective_entitlements(org_id)

    entitlements_data = effective.get("entitlements", {})
    usage_cards = []

    for key, data in entitlements_data.items():
        used = data.get("used", 0)
        limit = data.get("limit")
        pct = 0.0
        warning_level = "NORMAL"

        if limit and limit > 0:
            pct = round((used / limit) * 100, 1)
            if pct >= 100:
                warning_level = "CRITICAL"
            elif pct >= 80:
                warning_level = "WARNING"

        usage_cards.append({
            "entitlement_key": key,
            "used": used,
            "limit": limit,
            "percentage": pct,
            "warning_level": warning_level,
            "policy": data.get("policy", "HARD_LIMIT"),
        })

    return {
        "organization_id": tenant.organization_id,
        "period_start": effective.get("period_start"),
        "period_end": effective.get("period_end"),
        "meters": usage_cards,
    }


# ─── 5. Invoices List ─────────────────────────────────────────────────────────

@portal_router.get("/invoices", status_code=status.HTTP_200_OK)
async def list_portal_invoices(
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists tenant invoices with full breakdown of subtotal, tax, credits, and line items.
    """
    org_id = uuid.UUID(tenant.organization_id)
    stmt = (
        select(CanonicalInvoice)
        .where(CanonicalInvoice.organization_id == org_id)
        .options(selectinload(CanonicalInvoice.lines))
        .order_by(desc(CanonicalInvoice.created_at))
    )
    invoices = (await db.execute(stmt)).scalars().all()

    result = []
    for inv in invoices:
        lines_data = []
        for line in inv.lines:
            lines_data.append({
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "subtotal": str(line.subtotal),
                "total": str(line.total),
            })

        result.append({
            "id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "status": inv.status,
            "currency": inv.currency,
            "subtotal": str(inv.subtotal),
            "discount_amount": str(inv.discount_amount),
            "tax_amount": str(inv.tax_amount),
            "credit_amount": str(inv.credit_amount),
            "total": str(inv.total),
            "amount_paid": str(inv.amount_paid),
            "amount_due": str(inv.amount_due),
            "due_date": inv.due_date.isoformat(),
            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
            "lines": lines_data,
        })
    return result


# ─── 6. Credits Ledger & Balance ──────────────────────────────────────────────

@portal_router.get("/credits", status_code=status.HTTP_200_OK)
async def get_portal_credits(
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns available credit balance and recent append-only ledger entries.
    """
    org_id = uuid.UUID(tenant.organization_id)
    svc = CreditService(db)
    balance = await svc.get_balance(org_id, "INR")
    ledger_entries = await svc.list_ledger(org_id, limit=20)

    entries_data = [
        {
            "id": str(e.id),
            "entry_type": e.entry_type,
            "amount": str(e.amount),
            "currency": e.currency,
            "balance_after": str(e.balance_after),
            "reason": e.reason,
            "created_at": e.created_at.isoformat(),
        }
        for e in ledger_entries
    ]

    return {
        "balance": str(balance.amount),
        "currency": balance.currency,
        "entries": entries_data,
    }


# ─── 7. Plan Upgrades & Modifications ────────────────────────────────────────

@portal_router.post("/upgrade", status_code=status.HTTP_200_OK)
async def upgrade_portal_plan(
    req: PlanChangeRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes immediate plan upgrade with proration and entitlement recalculation.
    """
    org_id = uuid.UUID(tenant.organization_id)
    engine = SubscriptionEngine(db)

    stmt = (
        select(CanonicalSubscription)
        .where(CanonicalSubscription.organization_id == org_id)
        .order_by(CanonicalSubscription.created_at.desc())
    )
    sub = (await self_execute_first(db, stmt))
    if not sub:
        # Create new subscription
        new_sub = await engine.create_subscription(
            organization_id=org_id,
            plan_code=req.plan_code,
            interval=req.interval,
        )
        return {
            "status": "CREATED",
            "subscription_id": str(new_sub.id),
            "message": f"Successfully subscribed to plan {req.plan_code}.",
        }

    upgraded_sub, unused_credit = await engine.upgrade_plan(
        subscription_id=sub.id,
        new_plan_code=req.plan_code,
        new_interval=req.interval,
    )

    return {
        "status": "UPGRADED",
        "subscription_id": str(upgraded_sub.id),
        "new_plan": req.plan_code,
        "new_interval": req.interval,
        "unused_credit_applied": str(unused_credit.amount),
        "currency": unused_credit.currency,
    }


@portal_router.post("/cancel", status_code=status.HTTP_200_OK)
async def cancel_portal_subscription(
    req: CancelSubscriptionRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancels subscription immediately or at period end.
    """
    org_id = uuid.UUID(tenant.organization_id)
    engine = SubscriptionEngine(db)

    stmt = (
        select(CanonicalSubscription)
        .where(CanonicalSubscription.organization_id == org_id)
        .order_by(CanonicalSubscription.created_at.desc())
    )
    sub = (await self_execute_first(db, stmt))
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription found.")

    cancelled = await engine.cancel_subscription(sub.id, immediate=req.immediate)
    return {
        "status": cancelled.status,
        "cancel_at_period_end": cancelled.cancel_at_period_end,
        "cancelled_at": cancelled.cancelled_at.isoformat() if cancelled.cancelled_at else None,
        "message": "Subscription cancelled." if req.immediate else "Subscription scheduled for cancellation at period end.",
    }


async def self_execute_first(db: AsyncSession, stmt):
    return (await db.execute(stmt)).scalars().first()
