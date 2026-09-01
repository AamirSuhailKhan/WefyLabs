"""
MarketService & MarketActivationService
========================================
Markets are sub-country geographic/business units.
Organizations must be explicitly activated for each market.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.global_models import Market, MarketConfiguration, MarketRollout

logger = logging.getLogger(__name__)

# Required checklist items before a market can go GENERAL
ACTIVATION_CHECKLIST_KEYS = [
    "currency",
    "timezone",
    "language",
    "payment_provider",
    "whatsapp_provider",
    "lead_sources",
    "communication_policies",
    "calendar_business_hours",
    "property_schema",
    "compliance_policies",
    "consent_rules",
    "data_residency",
]


class MarketService:
    """
    Market registry and per-organization market access control.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_market(self, market_id: str) -> Optional[Market]:
        stmt = select(Market).where(Market.id == market_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Market]:
        stmt = select(Market).where(Market.slug == slug)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_markets_for_country(self, country_id: str) -> List[Market]:
        stmt = (
            select(Market)
            .where(and_(Market.country_id == country_id, Market.is_enabled == True))
            .order_by(Market.name)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_markets_for_organization(self, organization_id: str) -> List[Market]:
        """Return all markets the organization has an active rollout for."""
        stmt = (
            select(Market)
            .join(
                MarketRollout,
                and_(
                    MarketRollout.market_id == Market.id,
                    MarketRollout.organization_id == organization_id,
                    MarketRollout.rollout_status.in_(["BETA", "LIMITED", "GENERAL"]),
                )
            )
            .where(Market.is_enabled == True)
            .order_by(Market.name)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def is_market_active_for_org(self, organization_id: str, market_id: str) -> bool:
        """Check if an organization has access to a specific market."""
        stmt = select(MarketRollout).where(and_(
            MarketRollout.organization_id == organization_id,
            MarketRollout.market_id == market_id,
            MarketRollout.rollout_status.in_(["BETA", "LIMITED", "GENERAL"]),
        ))
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_market_config(
        self,
        organization_id: str,
        market_id: str,
    ) -> Optional[MarketConfiguration]:
        stmt = (
            select(MarketConfiguration)
            .where(and_(
                MarketConfiguration.organization_id == organization_id,
                MarketConfiguration.market_id == market_id,
                MarketConfiguration.is_enabled == True,
            ))
            .order_by(MarketConfiguration.version.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def to_api_dict(self, market: Market) -> dict:
        return {
            "id": str(market.id),
            "name": market.name,
            "slug": market.slug,
            "display_name": market.display_name,
            "timezone": market.timezone,
            "currency_code": market.currency_code,
            "language_codes": market.language_codes,
            "weekend_days": market.weekend_days,
            "property_type_codes": market.property_type_codes,
            "lead_source_codes": market.lead_source_codes,
            "launch_status": market.launch_status,
            "is_enabled": market.is_enabled,
        }


class MarketActivationService:
    """
    Manages the market rollout state machine.
    Ensures no market goes GENERAL without completing the activation checklist.
    """

    VALID_TRANSITIONS = {
        "INTERNAL": ["BETA", "SUSPENDED"],
        "BETA": ["LIMITED", "INTERNAL", "SUSPENDED"],
        "LIMITED": ["GENERAL", "BETA", "SUSPENDED"],
        "GENERAL": ["SUSPENDED"],
        "SUSPENDED": ["BETA"],
    }

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_rollout(self, organization_id: str, market_id: str) -> Optional[MarketRollout]:
        stmt = select(MarketRollout).where(and_(
            MarketRollout.organization_id == organization_id,
            MarketRollout.market_id == market_id,
        ))
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def initialize_rollout(self, organization_id: str, market_id: str) -> MarketRollout:
        """Create an INTERNAL rollout entry for an org+market pair."""
        rollout = MarketRollout(
            organization_id=organization_id,
            market_id=market_id,
            rollout_status="INTERNAL",
            checklist_completed={k: False for k in ACTIVATION_CHECKLIST_KEYS},
        )
        self._db.add(rollout)
        await self._db.flush()
        return rollout

    async def complete_checklist_item(
        self,
        organization_id: str,
        market_id: str,
        item_key: str,
    ) -> MarketRollout:
        """Mark a checklist item as complete."""
        rollout = await self.get_rollout(organization_id, market_id)
        if not rollout:
            rollout = await self.initialize_rollout(organization_id, market_id)

        checklist = dict(rollout.checklist_completed or {})
        checklist[item_key] = True
        rollout.checklist_completed = checklist
        await self._db.flush()
        return rollout

    async def can_advance_to_general(self, organization_id: str, market_id: str) -> tuple[bool, list[str]]:
        """Check if all required checklist items are complete."""
        rollout = await self.get_rollout(organization_id, market_id)
        if not rollout:
            return False, ACTIVATION_CHECKLIST_KEYS

        checklist = rollout.checklist_completed or {}
        incomplete = [k for k in ACTIVATION_CHECKLIST_KEYS if not checklist.get(k, False)]
        return len(incomplete) == 0, incomplete

    async def advance_status(
        self,
        organization_id: str,
        market_id: str,
        target_status: str,
    ) -> tuple[bool, str]:
        """
        Advance market rollout status.
        Returns (success, message).
        """
        rollout = await self.get_rollout(organization_id, market_id)
        if not rollout:
            return False, "Rollout record not found. Initialize rollout first."

        current = rollout.rollout_status
        allowed_targets = self.VALID_TRANSITIONS.get(current, [])

        if target_status not in allowed_targets:
            return False, f"Cannot transition from {current} to {target_status}. Allowed: {allowed_targets}"

        # GENERAL requires full checklist
        if target_status == "GENERAL":
            can_go, incomplete = await self.can_advance_to_general(organization_id, market_id)
            if not can_go:
                return False, f"Checklist incomplete. Missing: {incomplete}"

        rollout.rollout_status = target_status

        if target_status == "GENERAL":
            from datetime import datetime, timezone
            rollout.activated_at = datetime.now(timezone.utc)
        elif target_status == "SUSPENDED":
            from datetime import datetime, timezone
            rollout.suspended_at = datetime.now(timezone.utc)

        await self._db.flush()
        logger.info(f"[Market] Org {organization_id} market {market_id}: {current} → {target_status}")
        return True, f"Market status advanced to {target_status}."
