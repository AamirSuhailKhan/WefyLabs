"""
MarketFlagService — Country/Market-Aware Feature Flags
=======================================================
Controls feature availability per market, organization, and rollout percentage.

NEVER hardcode: if country == "AE": enable_feature()
Instead query: MarketFlagService.is_enabled("feature.golden_visa", market_id, org_id)

Flag evaluation order (most specific wins):
  1. Organization override (for a specific org in a specific market)
  2. Market-level flag
  3. Country-level flag (all markets in country)
  4. Global system default (always disabled unless explicitly enabled)

Supports:
  - Binary on/off flags
  - Percentage rollout (e.g., 25% of orgs in UAE get AI voice)
  - JSON config payloads per flag
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

# System-level flag defaults (global baseline — all OFF unless enabled per market/org)
SYSTEM_FLAG_DEFAULTS: Dict[str, bool] = {
    "communication.whatsapp":        False,
    "communication.sms":             False,
    "communication.email":           True,   # Email is on by default globally
    "ai.auto_reply":                 False,
    "ai.auto_book":                  False,
    "ai.voice":                      False,
    "property.advanced_filters":     False,
    "property.golden_visa_badge":    False,  # UAE only
    "property.rera_badge":           False,  # IN/AE only
    "property.hdb_qualification":    False,  # SG only
    "market.uae":                    False,
    "market.india":                  False,
    "market.saudi":                  False,
    "market.uk":                     False,
    "leads.csv_import":              True,
    "leads.bulk_whatsapp":           False,
    "analytics.revenue_reporting":   False,
    "billing.stripe":                False,
    "billing.razorpay":              False,
    "billing.tap":                   False,
}


class MarketFlagService:
    """
    Market and organization-aware feature flag evaluator.

    Usage:
        service = MarketFlagService(db)
        enabled = await service.is_enabled("ai.voice", market_id="dubai", org_id="org-1")
        config = await service.get_config("communication.whatsapp", market_id="dubai")
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._cache: Dict[str, bool] = {}

    async def is_enabled(
        self,
        flag_key: str,
        *,
        market_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,  # Used for rollout percentage hash
    ) -> bool:
        """
        Evaluate whether a feature flag is enabled for the given context.
        Evaluation order: Org override → Market flag → System default.
        """
        cache_key = f"{flag_key}|{market_id}|{organization_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        from app.models.global_models import MarketFeatureFlag

        # 1. Check org-level override (most specific)
        if organization_id and market_id:
            stmt = select(MarketFeatureFlag).where(and_(
                MarketFeatureFlag.flag_key == flag_key,
                MarketFeatureFlag.organization_id == organization_id,
                MarketFeatureFlag.market_id == market_id,
            )).limit(1)
            result = await self._db.execute(stmt)
            flag = result.scalar_one_or_none()
            if flag:
                enabled = self._apply_rollout(flag, user_id)
                self._cache[cache_key] = enabled
                return enabled

        # 2. Check market-level flag
        if market_id:
            stmt = select(MarketFeatureFlag).where(and_(
                MarketFeatureFlag.flag_key == flag_key,
                MarketFeatureFlag.market_id == market_id,
                MarketFeatureFlag.organization_id.is_(None),
            )).limit(1)
            result = await self._db.execute(stmt)
            flag = result.scalar_one_or_none()
            if flag:
                enabled = self._apply_rollout(flag, user_id)
                self._cache[cache_key] = enabled
                return enabled

        # 3. System default
        default = SYSTEM_FLAG_DEFAULTS.get(flag_key, False)
        self._cache[cache_key] = default
        return default

    async def get_config(
        self,
        flag_key: str,
        *,
        market_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the JSON config payload for a feature flag.
        Returns None if flag not found or has no config.
        """
        from app.models.global_models import MarketFeatureFlag

        conditions = [MarketFeatureFlag.flag_key == flag_key]
        if organization_id:
            conditions.append(MarketFeatureFlag.organization_id == organization_id)
        if market_id:
            conditions.append(MarketFeatureFlag.market_id == market_id)

        stmt = select(MarketFeatureFlag).where(and_(*conditions)).limit(1)
        result = await self._db.execute(stmt)
        flag = result.scalar_one_or_none()

        return flag.config_json if flag else None

    async def set_flag(
        self,
        flag_key: str,
        is_enabled: bool,
        *,
        market_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        rollout_percentage: int = 100,
        config_json: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create or update a feature flag."""
        from app.models.global_models import MarketFeatureFlag

        stmt = select(MarketFeatureFlag).where(and_(
            MarketFeatureFlag.flag_key == flag_key,
            MarketFeatureFlag.market_id == market_id if market_id else MarketFeatureFlag.market_id.is_(None),
            MarketFeatureFlag.organization_id == organization_id if organization_id else MarketFeatureFlag.organization_id.is_(None),
        )).limit(1)
        result = await self._db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.is_enabled = is_enabled
            existing.rollout_percentage = rollout_percentage
            if config_json is not None:
                existing.config_json = config_json
        else:
            self._db.add(MarketFeatureFlag(
                flag_key=flag_key,
                is_enabled=is_enabled,
                market_id=market_id,
                organization_id=organization_id,
                rollout_percentage=rollout_percentage,
                config_json=config_json,
            ))

        await self._db.flush()
        # Invalidate cache for this flag
        keys_to_clear = [k for k in self._cache if k.startswith(f"{flag_key}|")]
        for k in keys_to_clear:
            del self._cache[k]

        logger.info(f"[FeatureFlags] {flag_key} set to {is_enabled} (rollout={rollout_percentage}%) market={market_id} org={organization_id}")

    async def get_all_flags(
        self,
        market_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Dict[str, bool]:
        """Return all flags and their effective state for a market/org."""
        result = {}
        for flag_key in SYSTEM_FLAG_DEFAULTS:
            result[flag_key] = await self.is_enabled(
                flag_key,
                market_id=market_id,
                organization_id=organization_id,
            )
        return result

    @staticmethod
    def _apply_rollout(flag, user_id: Optional[str]) -> bool:
        """
        Apply percentage rollout using deterministic hash.
        Same user always gets the same flag value (sticky rollout).
        """
        if not flag.is_enabled:
            return False
        if flag.rollout_percentage >= 100:
            return True
        if flag.rollout_percentage <= 0:
            return False

        # Deterministic bucket assignment via hash
        seed = f"{flag.flag_key}:{user_id or 'anonymous'}"
        hash_int = int(hashlib.md5(seed.encode()).hexdigest(), 16)
        bucket = hash_int % 100
        return bucket < flag.rollout_percentage
