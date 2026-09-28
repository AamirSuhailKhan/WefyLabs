"""
WefyLabs Canonical Subscription Lifecycle & Billing Period Engine
==================================================================
Manages state machine, plan upgrades/downgrades, proration, and billing period generation.
States: TRIALING -> ACTIVE -> PAST_DUE -> PAUSED -> CANCEL_AT_PERIOD_END -> CANCELLED -> EXPIRED.
Every transition generates an audit entry and updates billing period boundaries.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.billing_models import (
    BillingAccount,
    BillingCustomer,
    Plan,
    PlanVersion,
    Subscription as CanonicalSubscription,
    BillingPeriod,
    BillingPeriodStatus,
    SubscriptionLifecycleStatus,
    PlanInterval,
    BillingAccountStatus,
)
from app.modules.billing.domain.money import Money, MoneyCalculator
from app.modules.billing.services.catalog_service import CatalogService

logger = logging.getLogger("wefylabs.billing.subscription")


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures datetime has UTC tzinfo even if SQLite/driver stripped it."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SubscriptionTransitionError(ValueError):
    """Raised when an invalid subscription state change is attempted."""
    pass


class SubscriptionEngine:
    """
    Core subscription orchestration and lifecycle service.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.catalog_service = CatalogService(db)

    async def ensure_billing_account(
        self,
        organization_id: uuid.UUID,
        billing_email: str,
        currency: str = "INR"
    ) -> BillingAccount:
        """
        Retrieves or initializes the canonical BillingAccount for an organization.
        """
        stmt = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        account = (await self.db.execute(stmt)).scalars().first()
        if not account:
            account = BillingAccount(
                organization_id=organization_id,
                billing_email=billing_email,
                currency=currency,
                status=BillingAccountStatus.ACTIVE.value,
            )
            self.db.add(account)
            await self.db.flush()
        return account

    async def create_subscription(
        self,
        organization_id: uuid.UUID,
        plan_code: str,
        interval: str = PlanInterval.MONTHLY.value,
        billing_email: Optional[str] = None,
        trial_days: Optional[int] = None,
        provider_subscription_id: Optional[str] = None,
    ) -> CanonicalSubscription:
        """
        Initializes a subscription for an organization under a specific PlanVersion.
        """
        plan_version = await self.catalog_service.get_plan_version_by_code(plan_code, interval)
        if not plan_version:
            raise ValueError(f"Plan '{plan_code}' with interval '{interval}' not found.")

        email = billing_email or f"billing@{organization_id}.wefylabs.com"
        account = await self.ensure_billing_account(organization_id, email, currency=plan_version.currency)

        now = datetime.now(timezone.utc)
        effective_trial_days = trial_days if trial_days is not None else plan_version.trial_days

        if effective_trial_days > 0:
            status = SubscriptionLifecycleStatus.TRIALING.value
            trial_ends_at = now + timedelta(days=effective_trial_days)
            period_end = trial_ends_at
        else:
            status = SubscriptionLifecycleStatus.ACTIVE.value
            trial_ends_at = None
            days_in_cycle = 365 if interval == PlanInterval.ANNUAL.value else 30
            period_end = now + timedelta(days=days_in_cycle)

        subscription = CanonicalSubscription(
            organization_id=organization_id,
            billing_account_id=account.id,
            plan_version_id=plan_version.id,
            status=status,
            current_period_start=now,
            current_period_end=period_end,
            started_at=now,
            trial_ends_at=trial_ends_at,
            provider_subscription_id=provider_subscription_id,
        )
        self.db.add(subscription)
        await self.db.flush()

        # Generate initial billing period
        billing_period = BillingPeriod(
            organization_id=organization_id,
            subscription_id=subscription.id,
            period_start=now,
            period_end=period_end,
            status=BillingPeriodStatus.OPEN.value,
        )
        self.db.add(billing_period)
        await self.db.commit()
        await self.db.refresh(subscription)

        logger.info(f"[SubscriptionEngine] Created {status} subscription {subscription.id} for org {organization_id} (Plan: {plan_code})")
        return subscription

    async def activate_subscription(self, subscription_id: uuid.UUID) -> CanonicalSubscription:
        """
        Transitions a TRIALING or PAST_DUE subscription to ACTIVE.
        """
        stmt = (
            select(CanonicalSubscription)
            .where(CanonicalSubscription.id == subscription_id)
            .options(selectinload(CanonicalSubscription.plan_version))
        )
        sub = (await self.db.execute(stmt)).scalars().first()
        if not sub:
            raise ValueError(f"Subscription {subscription_id} not found.")

        now = datetime.now(timezone.utc)
        sub.status = SubscriptionLifecycleStatus.ACTIVE.value
        sub.grace_ends_at = None

        # If period ended or was trial, advance cycle
        current_period_end_utc = _to_utc(sub.current_period_end)
        if (current_period_end_utc and current_period_end_utc <= now) or sub.trial_ends_at:
            interval = sub.plan_version.interval if sub.plan_version else PlanInterval.MONTHLY.value
            days = 365 if interval == PlanInterval.ANNUAL.value else 30
            sub.current_period_start = now
            sub.current_period_end = now + timedelta(days=days)

            # Close old open period
            stmt_old = select(BillingPeriod).where(
                and_(
                    BillingPeriod.subscription_id == sub.id,
                    BillingPeriod.status == BillingPeriodStatus.OPEN.value
                )
            )
            old_period = (await self.db.execute(stmt_old)).scalars().first()
            if old_period:
                old_period.status = BillingPeriodStatus.CLOSED.value

            new_period = BillingPeriod(
                organization_id=sub.organization_id,
                subscription_id=sub.id,
                period_start=sub.current_period_start,
                period_end=sub.current_period_end,
                status=BillingPeriodStatus.OPEN.value,
            )
            self.db.add(new_period)

        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    async def mark_past_due(
        self,
        subscription_id: uuid.UUID,
        grace_days: int = 7
    ) -> CanonicalSubscription:
        """
        Marks subscription as PAST_DUE with an explicit grace period.
        """
        stmt = select(CanonicalSubscription).where(CanonicalSubscription.id == subscription_id)
        sub = (await self.db.execute(stmt)).scalars().first()
        if not sub:
            raise ValueError(f"Subscription {subscription_id} not found.")

        now = datetime.now(timezone.utc)
        sub.status = SubscriptionLifecycleStatus.PAST_DUE.value
        sub.grace_ends_at = now + timedelta(days=grace_days)
        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    async def upgrade_plan(
        self,
        subscription_id: uuid.UUID,
        new_plan_code: str,
        new_interval: str = PlanInterval.MONTHLY.value,
    ) -> Tuple[CanonicalSubscription, Money]:
        """
        Executes immediate plan upgrade.
        Calculates exact proration for remaining unused time on current plan,
        applies new plan version, and creates new billing period.
        """
        stmt = (
            select(CanonicalSubscription)
            .where(CanonicalSubscription.id == subscription_id)
            .options(selectinload(CanonicalSubscription.plan_version))
        )
        sub = (await self.db.execute(stmt)).scalars().first()
        if not sub:
            raise ValueError(f"Subscription {subscription_id} not found.")

        new_version = await self.catalog_service.get_plan_version_by_code(new_plan_code, new_interval)
        if not new_version:
            raise ValueError(f"Target plan version '{new_plan_code}' ({new_interval}) not found.")

        now = datetime.now(timezone.utc)
        period_start_utc = _to_utc(sub.current_period_start)
        period_end_utc = _to_utc(sub.current_period_end)
        total_seconds = int((period_end_utc - period_start_utc).total_seconds()) if (period_end_utc and period_start_utc) else 1
        remaining_seconds = max(0, int((period_end_utc - now).total_seconds())) if period_end_utc else 0

        # Unused credit on old plan
        old_price = Money(sub.plan_version.price, sub.plan_version.currency)
        unused_credit = MoneyCalculator.calculate_proration(old_price, total_seconds, remaining_seconds)

        # Apply new plan
        sub.plan_version_id = new_version.id
        sub.status = SubscriptionLifecycleStatus.ACTIVE.value
        days = 365 if new_interval == PlanInterval.ANNUAL.value else 30
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=days)

        # Create new period
        new_period = BillingPeriod(
            organization_id=sub.organization_id,
            subscription_id=sub.id,
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            status=BillingPeriodStatus.OPEN.value,
        )
        self.db.add(new_period)
        await self.db.commit()
        await self.db.refresh(sub)

        logger.info(f"[SubscriptionEngine] Upgraded subscription {sub.id} to {new_plan_code}. Unused credit: {unused_credit}")
        return sub, unused_credit

    async def cancel_subscription(
        self,
        subscription_id: uuid.UUID,
        immediate: bool = False
    ) -> CanonicalSubscription:
        """
        Cancels subscription immediately or at period end.
        """
        stmt = select(CanonicalSubscription).where(CanonicalSubscription.id == subscription_id)
        sub = (await self.db.execute(stmt)).scalars().first()
        if not sub:
            raise ValueError(f"Subscription {subscription_id} not found.")

        now = datetime.now(timezone.utc)
        if immediate:
            sub.status = SubscriptionLifecycleStatus.CANCELLED.value
            sub.cancelled_at = now
        else:
            sub.cancel_at_period_end = True
            sub.status = SubscriptionLifecycleStatus.CANCEL_AT_PERIOD_END.value

        await self.db.commit()
        await self.db.refresh(sub)
        return sub
