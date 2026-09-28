"""
WefyLabs Canonical Entitlement Engine & Pre-Action Authorization Service
========================================================================
Authoritative server-side entitlement evaluation and consumption:
- Deterministic, fail-closed enforcement outside the LLM.
- Multi-tenant isolated via organization_id.
- Evaluates Subscription lifecycle (ACTIVE, TRIALING, PAST_DUE with grace, CANCELLED, EXPIRED).
- Supports boolean capabilities, integer limits, unlimited quotas, and overage policies.
- Append-only consumption and pre-action reservation/commit tracking.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.billing_models import (
    Subscription as CanonicalSubscription,
    PlanVersion,
    PlanEntitlement,
    EntitlementGrant,
    EntitlementConsumption,
    BillingPeriod,
    BillingPeriodStatus,
    SubscriptionLifecycleStatus,
    EntitlementType,
    LimitEnforcementPolicy,
)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures datetime has UTC tzinfo even if SQLite/driver stripped it."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class EntitlementExceededError(Exception):
    """Raised when an action exceeds the authorized entitlement quota under a HARD_LIMIT policy."""
    def __init__(self, key: str, requested: int, limit: Optional[int], current: int, reason: str):
        self.key = key
        self.requested = requested
        self.limit = limit
        self.current = current
        self.reason = reason
        super().__init__(f"Entitlement '{key}' exceeded: current={current}, limit={limit}, requested={requested}. Reason: {reason}")


class SubscriptionInactiveError(Exception):
    """Raised when an organization attempts paid actions without an active or grace subscription."""
    pass


@dataclass
class EntitlementCheckResult:
    allowed: bool
    entitlement_key: str
    current_usage: int
    limit_value: Optional[int]
    remaining: Optional[int]
    policy: str
    reason: Optional[str] = None
    subscription_status: str = "NONE"


class EntitlementService:
    """
    Central entitlement and quota enforcement service.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active_subscription(self, organization_id: uuid.UUID) -> Optional[CanonicalSubscription]:
        """
        Resolves current subscription for the organization.
        """
        stmt = (
            select(CanonicalSubscription)
            .where(CanonicalSubscription.organization_id == organization_id)
            .options(
                selectinload(CanonicalSubscription.plan_version).selectinload(PlanVersion.entitlements)
            )
            .order_by(CanonicalSubscription.created_at.desc())
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def get_current_billing_period(
        self,
        organization_id: uuid.UUID,
        subscription_id: uuid.UUID
    ) -> Optional[BillingPeriod]:
        """
        Resolves open billing period for the organization.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(BillingPeriod)
            .where(
                and_(
                    BillingPeriod.organization_id == organization_id,
                    BillingPeriod.subscription_id == subscription_id,
                    BillingPeriod.period_start <= now,
                    BillingPeriod.period_end > now,
                )
            )
        )
        period = (await self.db.execute(stmt)).scalars().first()
        if not period:
            # Fallback to any open period
            stmt_open = (
                select(BillingPeriod)
                .where(
                    and_(
                        BillingPeriod.organization_id == organization_id,
                        BillingPeriod.subscription_id == subscription_id,
                        BillingPeriod.status == BillingPeriodStatus.OPEN.value,
                    )
                )
                .order_by(BillingPeriod.period_start.desc())
            )
            period = (await self.db.execute(stmt_open)).scalars().first()
        return period

    async def check_entitlement(
        self,
        organization_id: uuid.UUID,
        entitlement_key: str,
        requested_quantity: int = 1
    ) -> EntitlementCheckResult:
        """
        Deterministic, server-side entitlement check.
        Returns EntitlementCheckResult detailing if allowed, limits, and reasons.
        """
        now = datetime.now(timezone.utc)
        sub = await self.get_active_subscription(organization_id)

        # 1. Check custom overrides / direct grants first
        stmt_grant = (
            select(EntitlementGrant)
            .where(
                and_(
                    EntitlementGrant.organization_id == organization_id,
                    EntitlementGrant.entitlement_key == entitlement_key,
                    EntitlementGrant.is_active == True,
                    EntitlementGrant.valid_from <= now,
                )
            )
            .order_by(EntitlementGrant.created_at.desc())
        )
        grant = (await self.db.execute(stmt_grant)).scalars().first()
        if grant:
            valid_to_utc = _to_utc(grant.valid_to)
            if valid_to_utc and valid_to_utc < now:
                grant = None

        # 2. If no subscription and no override grant, fail closed
        if not sub and not grant:
            return EntitlementCheckResult(
                allowed=False,
                entitlement_key=entitlement_key,
                current_usage=0,
                limit_value=0,
                remaining=0,
                policy=LimitEnforcementPolicy.HARD_LIMIT.value,
                reason="No active subscription found for organization.",
                subscription_status="NONE"
            )

        sub_status = sub.status if sub else "OVERRIDE"

        # 3. Check Subscription Lifecycle & Grace Period
        if sub:
            if sub.status in (SubscriptionLifecycleStatus.EXPIRED.value, SubscriptionLifecycleStatus.CANCELLED.value):
                return EntitlementCheckResult(
                    allowed=False,
                    entitlement_key=entitlement_key,
                    current_usage=0,
                    limit_value=0,
                    remaining=0,
                    policy=LimitEnforcementPolicy.HARD_LIMIT.value,
                    reason=f"Subscription is {sub.status}.",
                    subscription_status=sub_status
                )
            elif sub.status == SubscriptionLifecycleStatus.PAST_DUE.value:
                # Check if still inside grace period
                grace_ends_at_utc = _to_utc(sub.grace_ends_at)
                if not grace_ends_at_utc or grace_ends_at_utc < now:
                    return EntitlementCheckResult(
                        allowed=False,
                        entitlement_key=entitlement_key,
                        current_usage=0,
                        limit_value=0,
                        remaining=0,
                        policy=LimitEnforcementPolicy.HARD_LIMIT.value,
                        reason="Subscription past due and grace period expired.",
                        subscription_status=sub_status
                    )

        # 4. Resolve limit & policy
        limit_val: Optional[int] = None
        policy: str = LimitEnforcementPolicy.HARD_LIMIT.value
        ent_type: str = EntitlementType.INTEGER_LIMIT.value

        if grant:
            if grant.boolean_value is not None:
                return EntitlementCheckResult(
                    allowed=grant.boolean_value,
                    entitlement_key=entitlement_key,
                    current_usage=0,
                    limit_value=None,
                    remaining=None,
                    policy=LimitEnforcementPolicy.HARD_LIMIT.value,
                    reason="Granted via custom organization override.",
                    subscription_status=sub_status
                )
            limit_val = grant.limit_value
        elif sub and sub.plan_version:
            matching_ent = next(
                (e for e in sub.plan_version.entitlements if e.entitlement_key == entitlement_key),
                None
            )
            if not matching_ent:
                return EntitlementCheckResult(
                    allowed=False,
                    entitlement_key=entitlement_key,
                    current_usage=0,
                    limit_value=0,
                    remaining=0,
                    policy=LimitEnforcementPolicy.HARD_LIMIT.value,
                    reason=f"Feature '{entitlement_key}' not included in plan {sub.plan_version.plan_id}.",
                    subscription_status=sub_status
                )

            if matching_ent.entitlement_type == EntitlementType.BOOLEAN.value:
                return EntitlementCheckResult(
                    allowed=bool(matching_ent.boolean_value),
                    entitlement_key=entitlement_key,
                    current_usage=0,
                    limit_value=None,
                    remaining=None,
                    policy=matching_ent.enforcement_policy,
                    reason=None if matching_ent.boolean_value else "Feature disabled in plan.",
                    subscription_status=sub_status
                )

            if matching_ent.entitlement_type == EntitlementType.UNLIMITED.value or matching_ent.limit_value is None:
                return EntitlementCheckResult(
                    allowed=True,
                    entitlement_key=entitlement_key,
                    current_usage=0,
                    limit_value=None,
                    remaining=None,
                    policy=LimitEnforcementPolicy.UNLIMITED.value,
                    reason=None,
                    subscription_status=sub_status
                )

            limit_val = matching_ent.limit_value
            policy = matching_ent.enforcement_policy
            ent_type = matching_ent.entitlement_type

        # 5. Calculate current usage in period
        current_period = await self.get_current_billing_period(organization_id, sub.id) if sub else None
        period_id = current_period.id if current_period else None

        usage_stmt = select(func.coalesce(func.sum(EntitlementConsumption.quantity), 0)).where(
            and_(
                EntitlementConsumption.organization_id == organization_id,
                EntitlementConsumption.entitlement_key == entitlement_key,
            )
        )
        if period_id:
            usage_stmt = usage_stmt.where(EntitlementConsumption.billing_period_id == period_id)

        current_usage = int((await self.db.execute(usage_stmt)).scalar() or 0)
        remaining = max(0, limit_val - current_usage) if limit_val is not None else None

        if limit_val is not None and (current_usage + requested_quantity) > limit_val:
            if policy == LimitEnforcementPolicy.HARD_LIMIT.value:
                return EntitlementCheckResult(
                    allowed=False,
                    entitlement_key=entitlement_key,
                    current_usage=current_usage,
                    limit_value=limit_val,
                    remaining=remaining,
                    policy=policy,
                    reason=f"Quota of {limit_val} reached for {entitlement_key} (current: {current_usage}).",
                    subscription_status=sub_status
                )
            elif policy in (LimitEnforcementPolicy.SOFT_LIMIT.value, LimitEnforcementPolicy.OVERAGE.value):
                # Allowed with warning / overage charge
                return EntitlementCheckResult(
                    allowed=True,
                    entitlement_key=entitlement_key,
                    current_usage=current_usage,
                    limit_value=limit_val,
                    remaining=0,
                    policy=policy,
                    reason="Soft limit / overage policy active.",
                    subscription_status=sub_status
                )

        return EntitlementCheckResult(
            allowed=True,
            entitlement_key=entitlement_key,
            current_usage=current_usage,
            limit_value=limit_val,
            remaining=remaining,
            policy=policy,
            reason=None,
            subscription_status=sub_status
        )

    async def consume_entitlement(
        self,
        organization_id: uuid.UUID,
        entitlement_key: str,
        quantity: int = 1,
        action_reference: Optional[str] = None
    ) -> EntitlementCheckResult:
        """
        Verifies entitlement and writes consumption record atomically.
        Raises EntitlementExceededError if hard limit violated.
        """
        check = await self.check_entitlement(organization_id, entitlement_key, requested_quantity=quantity)
        if not check.allowed:
            raise EntitlementExceededError(
                key=entitlement_key,
                requested=quantity,
                limit=check.limit_value,
                current=check.current_usage,
                reason=check.reason or "Quota exceeded."
            )

        sub = await self.get_active_subscription(organization_id)
        current_period = await self.get_current_billing_period(organization_id, sub.id) if sub else None

        consumption = EntitlementConsumption(
            organization_id=organization_id,
            entitlement_key=entitlement_key,
            billing_period_id=current_period.id if current_period else None,
            quantity=quantity,
            action_reference=action_reference,
            consumed_at=datetime.now(timezone.utc),
        )
        self.db.add(consumption)
        await self.db.commit()

        # Recalculate remaining
        new_usage = check.current_usage + quantity
        new_remaining = max(0, check.limit_value - new_usage) if check.limit_value is not None else None
        return EntitlementCheckResult(
            allowed=True,
            entitlement_key=entitlement_key,
            current_usage=new_usage,
            limit_value=check.limit_value,
            remaining=new_remaining,
            policy=check.policy,
            reason=None,
            subscription_status=check.subscription_status
        )

    async def get_effective_entitlements(self, organization_id: uuid.UUID) -> Dict[str, Any]:
        """
        Returns complete mapping of entitlements, limits, usage, and status for dashboard & API.
        """
        sub = await self.get_active_subscription(organization_id)
        if not sub or not sub.plan_version:
            return {
                "subscription_status": "NONE",
                "plan_code": "none",
                "entitlements": {},
            }

        plan_code = sub.plan_version.plan.code if hasattr(sub.plan_version, "plan") and sub.plan_version.plan else "unknown"
        entitlements_map: Dict[str, Any] = {}

        for ent in sub.plan_version.entitlements:
            check = await self.check_entitlement(organization_id, ent.entitlement_key, requested_quantity=0)
            entitlements_map[ent.entitlement_key] = {
                "type": ent.entitlement_type,
                "limit": check.limit_value,
                "used": check.current_usage,
                "remaining": check.remaining,
                "allowed": check.allowed,
                "policy": check.policy,
                "boolean_value": ent.boolean_value,
            }

        return {
            "subscription_status": sub.status,
            "plan_code": plan_code,
            "plan_interval": sub.plan_version.interval,
            "period_start": sub.current_period_start.isoformat(),
            "period_end": sub.current_period_end.isoformat(),
            "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
            "entitlements": entitlements_map,
        }
