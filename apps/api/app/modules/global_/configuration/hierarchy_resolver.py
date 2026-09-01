"""
ConfigurationHierarchyResolver — Production Config Precedence Engine
=====================================================================
Resolves configuration values using the full hierarchy:

  System Default
     ↓
  Country Config
     ↓
  Market Config
     ↓
  Organization Config
     ↓
  Team Config
     ↓
  User Config
     ↓
  Lead/Customer Override (most specific)

More specific configuration ALWAYS overrides broader configuration
where permitted by policy.

Document precedence: Each resolution records WHY a value was chosen
(which level resolved it) for auditability.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


@dataclass
class ConfigResolution:
    """Result of a configuration resolution — value + provenance."""
    key: str
    value: Any
    resolved_from: str      # "user" | "team" | "org" | "market" | "country" | "system"
    resolved_at_id: Optional[str] = None   # The ID of the entity that provided the value
    is_default: bool = False
    override_chain: List[str] = field(default_factory=list)  # Full resolution path

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "resolved_from": self.resolved_from,
            "resolved_at_id": self.resolved_at_id,
            "is_default": self.is_default,
            "override_chain": self.override_chain,
        }


# System-level defaults (global baseline — lowest precedence)
SYSTEM_DEFAULTS: Dict[str, Any] = {
    "timezone":             "UTC",
    "currency_code":        "USD",
    "language_code":        "en",
    "date_format":          "YYYY-MM-DD",
    "area_unit":            "sqft",
    "working_days":         [0, 1, 2, 3, 4],   # Mon–Fri (0=Mon)
    "quiet_hours_start":    "21:00",
    "quiet_hours_end":      "08:00",
    "max_follow_up_days":   30,
    "ai_auto_reply":        False,
    "ai_auto_book":         False,
    "communication_channels": ["EMAIL"],
}


class ConfigurationHierarchyResolver:
    """
    Resolves configuration from the full hierarchy.
    Cached per request scope — do NOT cache across requests without TTL.

    Example:
        resolver = ConfigurationHierarchyResolver(db)
        result = await resolver.resolve(
            key="timezone",
            user_id="usr-1",
            team_id="team-1",
            organization_id="org-1",
            market_id="market-dubai",
            country_code="AE",
        )
        print(result.value)          # "Asia/Dubai"
        print(result.resolved_from)  # "market"
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._cache: Dict[str, ConfigResolution] = {}

    async def resolve(
        self,
        key: str,
        *,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        market_id: Optional[str] = None,
        country_code: Optional[str] = None,
        lead_id: Optional[str] = None,
    ) -> ConfigResolution:
        """
        Resolve a configuration key from the full hierarchy.
        Returns the most specific non-None value found.
        """
        cache_key = f"{key}|{user_id}|{team_id}|{organization_id}|{market_id}|{country_code}|{lead_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        chain = []

        # 1. Lead/Customer override (most specific)
        if lead_id:
            val = await self._from_lead(key, lead_id)
            chain.append(f"lead:{lead_id}")
            if val is not None:
                result = ConfigResolution(key=key, value=val, resolved_from="lead",
                                         resolved_at_id=lead_id, override_chain=chain)
                self._cache[cache_key] = result
                return result

        # 2. User config
        if user_id:
            val = await self._from_user(key, user_id)
            chain.append(f"user:{user_id}")
            if val is not None:
                result = ConfigResolution(key=key, value=val, resolved_from="user",
                                         resolved_at_id=user_id, override_chain=chain)
                self._cache[cache_key] = result
                return result

        # 3. Team config
        if team_id:
            val = await self._from_team(key, team_id)
            chain.append(f"team:{team_id}")
            if val is not None:
                result = ConfigResolution(key=key, value=val, resolved_from="team",
                                         resolved_at_id=team_id, override_chain=chain)
                self._cache[cache_key] = result
                return result

        # 4. Organization config
        if organization_id:
            val = await self._from_org(key, organization_id)
            chain.append(f"org:{organization_id}")
            if val is not None:
                result = ConfigResolution(key=key, value=val, resolved_from="org",
                                         resolved_at_id=organization_id, override_chain=chain)
                self._cache[cache_key] = result
                return result

        # 5. Market config
        if market_id:
            val = await self._from_market(key, market_id)
            chain.append(f"market:{market_id}")
            if val is not None:
                result = ConfigResolution(key=key, value=val, resolved_from="market",
                                         resolved_at_id=market_id, override_chain=chain)
                self._cache[cache_key] = result
                return result

        # 6. Country config
        if country_code:
            val = await self._from_country(key, country_code)
            chain.append(f"country:{country_code}")
            if val is not None:
                result = ConfigResolution(key=key, value=val, resolved_from="country",
                                         resolved_at_id=country_code, override_chain=chain)
                self._cache[cache_key] = result
                return result

        # 7. System default (lowest precedence)
        system_val = SYSTEM_DEFAULTS.get(key)
        chain.append("system")
        result = ConfigResolution(
            key=key,
            value=system_val,
            resolved_from="system",
            is_default=True,
            override_chain=chain,
        )
        self._cache[cache_key] = result
        logger.debug(f"[ConfigHierarchy] {key} resolved from system default: {system_val}")
        return result

    async def resolve_many(
        self,
        keys: List[str],
        **context
    ) -> Dict[str, ConfigResolution]:
        """Resolve multiple keys in one call."""
        return {key: await self.resolve(key, **context) for key in keys}

    def invalidate(self):
        """Clear request-scoped cache."""
        self._cache.clear()

    # ─── Level resolvers ──────────────────────────────────────────────────────

    async def _from_lead(self, key: str, lead_id: str) -> Optional[Any]:
        """Lead-level overrides (timezone, locale, language_code)."""
        try:
            from app.models.lead import Lead
            stmt = select(Lead).where(Lead.id == lead_id)
            result = await self._db.execute(stmt)
            lead = result.scalar_one_or_none()
            if not lead:
                return None
            mapping = {
                "timezone": getattr(lead, "timezone", None),
                "language_code": getattr(lead, "locale", None),
                "currency_code": getattr(lead, "budget_currency", None),
            }
            return mapping.get(key)
        except Exception as e:
            logger.debug(f"[ConfigHierarchy] Lead lookup failed for key={key}: {e}")
            return None

    async def _from_user(self, key: str, user_id: str) -> Optional[Any]:
        """User preferences (timezone, language from user profile)."""
        try:
            from app.models.user import User
            stmt = select(User).where(User.id == user_id)
            result = await self._db.execute(stmt)
            user = result.scalar_one_or_none()
            if not user:
                return None
            mapping = {
                "timezone": getattr(user, "timezone", None),
                "language_code": getattr(user, "language_code", None),
            }
            return mapping.get(key)
        except Exception as e:
            logger.debug(f"[ConfigHierarchy] User lookup failed for key={key}: {e}")
            return None

    async def _from_team(self, key: str, team_id: str) -> Optional[Any]:
        """Team-level config (team timezone, working days)."""
        # Teams may not have config models yet — safe fallback
        return None

    async def _from_org(self, key: str, organization_id: str) -> Optional[Any]:
        """Organization config — primary source for most non-lead values."""
        try:
            from app.models.organization import Organization
            stmt = select(Organization).where(Organization.id == organization_id)
            result = await self._db.execute(stmt)
            org = result.scalar_one_or_none()
            if not org:
                return None
            mapping = {
                "timezone":         getattr(org, "default_timezone", None),
                "currency_code":    getattr(org, "reporting_currency_code", None),
                "language_code":    getattr(org, "default_language", None),
                "country_code":     getattr(org, "country_code", None),
            }
            return mapping.get(key)
        except Exception as e:
            logger.debug(f"[ConfigHierarchy] Org lookup failed for key={key}: {e}")
            return None

    async def _from_market(self, key: str, market_id: str) -> Optional[Any]:
        """Market-level config — working days, timezone, currency."""
        try:
            from app.models.global_models import Market
            from sqlalchemy import select as sa_select
            stmt = sa_select(Market).where(Market.id == market_id)
            result = await self._db.execute(stmt)
            market = result.scalar_one_or_none()
            if not market:
                return None
            mapping = {
                "timezone":         market.timezone,
                "currency_code":    market.currency_code,
                "language_code":    (market.language_codes[0] if market.language_codes else None),
                "working_days":     [d for d in [0,1,2,3,4,5,6] if d not in (market.weekend_days or [])],
            }
            return mapping.get(key)
        except Exception as e:
            logger.debug(f"[ConfigHierarchy] Market lookup failed for key={key}: {e}")
            return None

    async def _from_country(self, key: str, country_code: str) -> Optional[Any]:
        """Country-level config — default timezone, currency, language."""
        try:
            from app.models.global_models import Country
            from sqlalchemy import select as sa_select
            stmt = sa_select(Country).where(Country.iso_alpha2 == country_code)
            result = await self._db.execute(stmt)
            country = result.scalar_one_or_none()
            if not country:
                return None
            mapping = {
                "timezone":         country.default_timezone,
                "currency_code":    country.default_currency_code,
                "language_code":    country.default_language_code,
            }
            return mapping.get(key)
        except Exception as e:
            logger.debug(f"[ConfigHierarchy] Country lookup failed for key={key}: {e}")
            return None
