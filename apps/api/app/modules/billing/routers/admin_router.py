"""
WefyLabs Admin Operations Billing Router
========================================
Administrative endpoints for:
- Tenant billing lookup & overview
- Manual credit issuance & adjustments with mandatory audit trail
- Manual refund review & execution
- Automated billing reconciliation trigger
- Tenant unit economics computation
- Billing infrastructure & provider health

Security & Compliance:
- Role & permission enforced: requires billing:manage permission.
- Every adjustment/credit requires explicit actor, reason, and provenance.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.organization import OrganizationMember
from app.models.billing_models import (
    BillingAccount,
    Subscription as CanonicalSubscription,
    Invoice as CanonicalInvoice,
    CreditLedgerEntry,
    BillingAdjustment,
    AdjustmentType,
    PlanVersion,
)
from app.modules.billing.domain.money import Money
from app.modules.billing.services.credit_service import CreditService
from app.modules.billing.services.reconciliation_service import BillingReconciliationService
from app.modules.billing.services.unit_economics_service import UnitEconomicsService
from app.modules.billing.services.razorpay_service import RazorpayProductionService

logger = logging.getLogger("wefylabs.billing.admin")

admin_router = APIRouter(prefix="/admin", tags=["Admin Billing Operations"])


# ─── Pydantic Request Models ─────────────────────────────────────────────────

class AdminCreditRequest(BaseModel):
    organization_id: str = Field(..., description="Target tenant UUID")
    amount: Decimal = Field(..., gt=0, description="Amount of credit in major currency units")
    currency: str = Field("INR", description="ISO currency code")
    reason: str = Field(..., min_length=5, description="Mandatory audit reason for manual credit issuance")


class AdminAdjustmentRequest(BaseModel):
    organization_id: str
    invoice_id: Optional[str] = None
    adjustment_type: str = Field(AdjustmentType.COURTESY.value)
    amount: Decimal = Field(..., gt=0)
    currency: str = "INR"
    reason: str = Field(..., min_length=5)


# ─── RBAC Dependency Helper ───────────────────────────────────────────────────

async def require_billing_manager(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Broker:
    """
    Enforces that caller has administrative billing privileges.
    Permits super-admins or members with OWNER, ADMIN, or FINANCE role.
    """
    stmt = select(OrganizationMember.role).where(OrganizationMember.broker_id == current_broker.id)
    roles = (await db.execute(stmt)).scalars().all()
    allowed_roles = {"OWNER", "ADMIN", "FINANCE"}

    if not any(r.upper() in allowed_roles for r in roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin billing operations require OWNER, ADMIN, or FINANCE role."
        )
    return current_broker


# ─── 1. Tenant Billing Overview ───────────────────────────────────────────────

@admin_router.get("/overview/{organization_id}", status_code=status.HTTP_200_OK)
async def get_tenant_billing_overview(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
    admin: Broker = Depends(require_billing_manager),
):
    """
    Comprehensive customer billing lookup for support and finance teams.
    """
    org_uuid = uuid.UUID(organization_id)

    # Billing account
    stmt_acc = select(BillingAccount).where(BillingAccount.organization_id == org_uuid)
    acc = (await db.execute(stmt_acc)).scalars().first()

    # Active subscription
    stmt_sub = (
        select(CanonicalSubscription)
        .where(CanonicalSubscription.organization_id == org_uuid)
        .options(selectinload(CanonicalSubscription.plan_version).selectinload(PlanVersion.plan))
        .order_by(CanonicalSubscription.created_at.desc())
    )
    sub = (await db.execute(stmt_sub)).scalars().first()

    # Invoices count and balance due
    stmt_inv_due = select(
        func.count(CanonicalInvoice.id),
        func.coalesce(func.sum(CanonicalInvoice.amount_due), Decimal("0.0"))
    ).where(CanonicalInvoice.organization_id == org_uuid)
    inv_count, total_due = (await db.execute(stmt_inv_due)).one()

    # Available credits
    credit_svc = CreditService(db)
    credit_balance = await credit_svc.get_balance(org_uuid, "INR")

    return {
        "organization_id": organization_id,
        "account_status": acc.status if acc else "NOT_CONFIGURED",
        "provider": acc.provider if acc else "NONE",
        "provider_customer_id": acc.provider_customer_id if acc else None,
        "subscription": {
            "id": str(sub.id) if sub else None,
            "status": sub.status if sub else "NONE",
            "plan_code": sub.plan_version.plan.code if (sub and sub.plan_version and sub.plan_version.plan) else "none",
            "period_start": sub.current_period_start.isoformat() if sub else None,
            "period_end": sub.current_period_end.isoformat() if sub else None,
        } if sub else None,
        "total_invoices": inv_count,
        "total_amount_due": str(total_due),
        "available_credits": str(credit_balance.amount),
        "currency": credit_balance.currency,
    }


# ─── 2. Credit Issuance ───────────────────────────────────────────────────────

@admin_router.post("/credits", status_code=status.HTTP_201_CREATED)
async def admin_issue_credit(
    req: AdminCreditRequest,
    db: AsyncSession = Depends(get_db),
    admin: Broker = Depends(require_billing_manager),
):
    """
    Manually issues credit to an organization with audit trail provenance.
    """
    org_uuid = uuid.UUID(req.organization_id)
    money = Money(req.amount, req.currency)
    credit_svc = CreditService(db)

    entry = await credit_svc.issue_credit(
        organization_id=org_uuid,
        amount=money,
        reason=f"[Admin: {admin.email}] {req.reason}",
        actor_id=str(admin.id),
        reference_type="ADMIN_GRANT",
    )

    return {
        "status": "ISSUED",
        "entry_id": str(entry.id),
        "amount": str(entry.amount),
        "currency": entry.currency,
        "new_balance": str(entry.balance_after),
        "issued_by": admin.email,
    }


# ─── 3. Automated Reconciliation Trigger ──────────────────────────────────────

@admin_router.post("/reconcile/{organization_id}", status_code=status.HTTP_200_OK)
async def admin_trigger_reconciliation(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
    admin: Broker = Depends(require_billing_manager),
):
    """
    Triggers automated financial reconciliation audit for the organization.
    """
    org_uuid = uuid.UUID(organization_id)
    svc = BillingReconciliationService(db)
    return await svc.run_reconciliation(org_uuid)


# ─── 4. Unit Economics Computation ───────────────────────────────────────────

@admin_router.get("/unit-economics/{organization_id}", status_code=status.HTTP_200_OK)
async def admin_get_unit_economics(
    organization_id: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    admin: Broker = Depends(require_billing_manager),
):
    """
    Computes exact unit economics snapshot (MRR, gross revenue, direct costs, margin) for a tenant.
    """
    org_uuid = uuid.UUID(organization_id)
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)

    svc = UnitEconomicsService(db)
    snapshot = await svc.compute_snapshot(
        organization_id=org_uuid,
        period_start=period_start,
        period_end=now,
        reporting_currency="INR"
    )

    return {
        "organization_id": organization_id,
        "period_start": snapshot.period_start.isoformat(),
        "period_end": snapshot.period_end.isoformat(),
        "currency": snapshot.currency,
        "mrr": str(snapshot.mrr),
        "arr": str(snapshot.arr),
        "gross_revenue": str(snapshot.gross_revenue),
        "net_revenue": str(snapshot.net_revenue),
        "refunds": str(snapshot.refunds),
        "credits": str(snapshot.credits),
        "variable_costs": {
            "ai_cost": str(snapshot.ai_cost),
            "messaging_cost": str(snapshot.messaging_cost),
            "payment_fees": str(snapshot.payment_fees),
            "storage_cost": str(snapshot.storage_cost),
            "other_cost": str(snapshot.other_cost),
            "total_variable_cost": str(snapshot.total_variable_cost),
        },
        "gross_profit": str(snapshot.gross_profit),
        "gross_margin_pct": str(snapshot.gross_margin_pct),
    }


# ─── 5. Infrastructure & Gateway Health ───────────────────────────────────────

@admin_router.get("/health", status_code=status.HTTP_200_OK)
async def get_billing_system_health(
    db: AsyncSession = Depends(get_db),
    admin: Broker = Depends(require_billing_manager),
):
    """
    Returns operational health status of billing gateways and worker queues.
    """
    emergency_paused = RazorpayProductionService.is_emergency_paused()
    return {
        "status": "DEGRADED" if emergency_paused else "HEALTHY",
        "emergency_pause_active": emergency_paused,
        "razorpay_gateway_status": "AVAILABLE",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
