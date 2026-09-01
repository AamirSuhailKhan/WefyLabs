"""
Cross-Country Identity Resolver & Customer Profile Engine
=========================================================
Spec §113–116 — Global Identity, Cross-Country Profiles & Market Segments.

Architectural Guarantees:
  1. Never merges two identities based on name matching alone.
  2. A customer operating in multiple countries (e.g. resident in India, investing in Dubai)
     maintains a single GlobalCustomer entity linked to multiple isolated MarketProfile records.
  3. Strict confidence-based matching:
     - Exact E.164 phone match: High Confidence (0.98)
     - Verified email match: High Confidence (0.95)
     - Name + fuzzy match: Low Confidence (<0.60) — NEVER auto-merges without human/policy approval.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.modules.global_.phone.phone_service import PhoneService

logger = logging.getLogger(__name__)


@dataclass
class MarketProfile:
    """Market-specific interaction context for a customer in a particular territory."""
    market_id: str
    country_code: str
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    currency_code: Optional[str] = None
    preferred_locations: List[str] = field(default_factory=list)
    preferred_property_types: List[str] = field(default_factory=list)
    timeline: Optional[str] = None
    inquiry_count: int = 0
    last_active_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GlobalCustomerProfile:
    """Canonical cross-market customer identity."""
    customer_id: str
    organization_id: str
    primary_name: str
    primary_phone_e164: Optional[str]
    primary_email: Optional[str]
    primary_country_code: Optional[str]
    preferred_language: str = "en"
    authorized_markets: List[str] = field(default_factory=list)
    market_profiles: Dict[str, MarketProfile] = field(default_factory=dict)
    identity_confidence: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "organization_id": self.organization_id,
            "primary_name": self.primary_name,
            "primary_phone": PhoneService.mask(self.primary_phone_e164),
            "primary_email": self.primary_email,
            "primary_country_code": self.primary_country_code,
            "preferred_language": self.preferred_language,
            "authorized_markets": self.authorized_markets,
            "market_profiles": {
                m_id: {
                    "market_id": mp.market_id,
                    "country_code": mp.country_code,
                    "budget_max": str(mp.budget_max) if mp.budget_max else None,
                    "currency_code": mp.currency_code,
                    "preferred_locations": mp.preferred_locations,
                    "preferred_property_types": mp.preferred_property_types,
                    "inquiry_count": mp.inquiry_count,
                }
                for m_id, mp in self.market_profiles.items()
            }
        }


class CrossCountryIdentityResolver:
    """
    Safely resolves and correlates customer records across international markets.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def resolve_identity(
        self,
        organization_id: str,
        phone: Optional[str],
        email: Optional[str],
        name: Optional[str] = None,
        market_id: Optional[str] = None,
        country_code: Optional[str] = None,
    ) -> Tuple[Optional[str], float, str]:
        """
        Resolves or associates incoming contact details with an existing customer.

        Returns:
            (customer_id, confidence_score, resolution_method)
        """
        from app.models.lead import Lead

        norm_phone = PhoneService.normalize_to_e164(phone, default_region=country_code) if phone else None
        clean_email = email.strip().lower() if email else None

        # 1. Exact E.164 Phone Match (Highest Confidence)
        if norm_phone:
            stmt = select(Lead).where(and_(
                Lead.organization_id == organization_id,
                Lead.phone == norm_phone,
            )).limit(1)
            res = await self._db.execute(stmt)
            match = res.scalar_one_or_none()
            if match:
                logger.info(f"[Identity] Resolved by Phone E.164 (match={match.id}, confidence=0.98)")
                return str(match.id), 0.98, "PHONE_E164_EXACT"

        # 2. Exact Email Match (High Confidence)
        if clean_email:
            stmt = select(Lead).where(and_(
                Lead.organization_id == organization_id,
                Lead.email == clean_email,
            )).limit(1)
            res = await self._db.execute(stmt)
            match = res.scalar_one_or_none()
            if match:
                logger.info(f"[Identity] Resolved by Verified Email (match={match.id}, confidence=0.95)")
                return str(match.id), 0.95, "EMAIL_EXACT"

        # 3. No Safe Match — DO NOT FUZZY MERGE ON NAME ALONE (Spec §113)
        logger.info("[Identity] No high-confidence identity match found. Treating as distinct individual.")
        return None, 0.0, "DISTINCT_NEW_IDENTITY"
