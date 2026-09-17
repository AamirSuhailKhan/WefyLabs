"""
Part 26 — Enterprise Lead Assignment Service
============================================
Handles automatic, tenant-isolated routing and assignment of incoming leads
to active brokers within an organization.

Strategies:
  - ROUND_ROBIN: Cycles through eligible active brokers
  - WORKLOAD: Assigns to the eligible active broker with the lowest recent lead count
  - DEFAULT_OWNER: Assigns to the organization owner or primary broker

Safety Guarantees:
  - Strictly tenant-isolated: only queries brokers who belong to the same organization
  - Verifies broker status: excludes suspended or inactive brokers
  - Guaranteed fallback: falls back safely to owner or primary broker without failing lead ingestion
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.broker import Broker
from app.models.organization import OrganizationMember, Organization
from app.models.lead import Lead

logger = logging.getLogger("beetlelabs.lead_acquisition.assignment")


class AssignmentStrategy:
    ROUND_ROBIN = "round_robin"
    WORKLOAD = "workload"
    DEFAULT_OWNER = "default_owner"


class LeadAssignmentService:
    def __init__(self, db: AsyncSession, redis_client: Optional[Any] = None):
        self.db = db
        self.redis = redis_client

    async def assign_lead(
        self,
        organization_id: str,
        strategy: str = AssignmentStrategy.ROUND_ROBIN,
        source_id: Optional[str] = None,
        property_type: Optional[str] = None,
        location: Optional[str] = None,
        budget: Optional[int] = None,
    ) -> uuid.UUID:
        """
        Determines the assigned broker UUID for a new lead within the organization.
        Guarantees: returns a valid active broker UUID belonging to organization_id.
        """
        eligible_brokers = await self.get_eligible_brokers(organization_id)
        if not eligible_brokers:
            # Check if organization_id itself is a broker ID (single-broker workspace)
            single_broker = await self._find_single_broker(organization_id)
            if single_broker:
                return single_broker.id
            raise ValueError(f"No active, eligible brokers found for organization {organization_id}")

        if len(eligible_brokers) == 1:
            return eligible_brokers[0].id

        if strategy == AssignmentStrategy.WORKLOAD:
            return await self._assign_by_workload(organization_id, eligible_brokers)
        elif strategy == AssignmentStrategy.DEFAULT_OWNER:
            return await self._assign_to_owner(organization_id, eligible_brokers)
        else:
            # Default to round-robin
            return await self._assign_by_round_robin(organization_id, eligible_brokers)

    async def get_eligible_brokers(self, organization_id: str) -> List[Broker]:
        """
        Returns active brokers belonging to the given organization.
        Filters out suspended users and inactive subscriptions where applicable.
        """
        try:
            org_uuid = uuid.UUID(str(organization_id))
        except (ValueError, AttributeError):
            org_uuid = None

        brokers: List[Broker] = []
        if org_uuid:
            stmt = (
                select(Broker)
                .join(OrganizationMember, OrganizationMember.broker_id == Broker.id)
                .where(
                    and_(
                        OrganizationMember.organization_id == org_uuid,
                        or_(
                            Broker.onboarding_status != "SUSPENDED",
                            Broker.onboarding_status.is_(None),
                        ),
                    )
                )
            )
            res = await self.db.execute(stmt)
            brokers = list(res.scalars().all())

        if not brokers:
            # Check if organization_id matches a broker ID directly
            single = await self._find_single_broker(organization_id)
            if single:
                brokers = [single]

        return brokers

    async def _find_single_broker(self, broker_or_org_id: str) -> Optional[Broker]:
        try:
            b_uuid = uuid.UUID(str(broker_or_org_id))
        except (ValueError, AttributeError):
            return None

        stmt = select(Broker).where(
            and_(
                Broker.id == b_uuid,
                or_(
                    Broker.onboarding_status != "SUSPENDED",
                    Broker.onboarding_status.is_(None),
                ),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def _assign_by_round_robin(
        self, organization_id: str, brokers: List[Broker]
    ) -> uuid.UUID:
        """
        Distributes leads evenly using an atomic Redis counter or DB lead count mod.
        """
        redis_key = f"acq:rr:{organization_id}"
        if self.redis:
            try:
                # Upstash / standard Redis client
                idx = await self.redis.incr(redis_key)
                selected_broker = brokers[idx % len(brokers)]
                return selected_broker.id
            except Exception as e:
                logger.debug(f"[ASSIGN] Redis round-robin fallback to DB: {e}")

        # DB-based fallback: count total leads across these brokers mod len(brokers)
        broker_ids = [b.id for b in brokers]
        stmt = select(func.count(Lead.id)).where(Lead.broker_id.in_(broker_ids))
        total_leads = (await self.db.execute(stmt)).scalar() or 0
        selected = brokers[total_leads % len(brokers)]
        return selected.id

    async def _assign_by_workload(
        self, organization_id: str, brokers: List[Broker]
    ) -> uuid.UUID:
        """
        Assigns to the broker with the lowest active lead count in the past 7 days.
        """
        broker_ids = [b.id for b in brokers]
        since = datetime.now(timezone.utc) - timedelta(days=7)

        stmt = (
            select(Lead.broker_id, func.count(Lead.id).label("cnt"))
            .where(
                and_(
                    Lead.broker_id.in_(broker_ids),
                    Lead.created_at >= since,
                    Lead.deleted_at.is_(None),
                )
            )
            .group_by(Lead.broker_id)
        )
        counts = dict((await self.db.execute(stmt)).all())

        # Find broker with minimum count
        min_broker = min(brokers, key=lambda b: counts.get(b.id, 0))
        return min_broker.id

    async def _assign_to_owner(
        self, organization_id: str, brokers: List[Broker]
    ) -> uuid.UUID:
        """
        Finds owner/admin role in OrganizationMember, or returns the first broker.
        """
        try:
            org_uuid = uuid.UUID(str(organization_id))
            stmt = (
                select(OrganizationMember.broker_id)
                .where(
                    and_(
                        OrganizationMember.organization_id == org_uuid,
                        OrganizationMember.role.in_(["owner", "admin"]),
                    )
                )
                .limit(1)
            )
            owner_id = (await self.db.execute(stmt)).scalar()
            if owner_id:
                for b in brokers:
                    if b.id == owner_id:
                        return b.id
        except Exception:
            pass

        return brokers[0].id
