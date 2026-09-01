"""
CountryService — Country Registry Service
=========================================
Provides DB-backed access to the global country registry.
Countries are seeded data — do NOT hardcode country logic in application code.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.global_models import Country

logger = logging.getLogger(__name__)


class CountryService:
    """
    Authoritative country registry service.
    All country lookups must go through here — never hardcode country details.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_iso2(self, iso2: str) -> Optional[Country]:
        """Get a country by ISO Alpha-2 code (e.g., 'AE', 'IN', 'GB')."""
        stmt = select(Country).where(Country.iso_alpha2 == iso2.upper())
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_countries(self) -> List[Country]:
        """Return all countries in ACTIVE launch status."""
        stmt = select(Country).where(
            and_(Country.launch_status == "ACTIVE", Country.is_enabled == True)
        ).order_by(Country.name)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> List[Country]:
        """Return all countries regardless of status."""
        stmt = select(Country).order_by(Country.name)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def is_enabled(self, iso2: str) -> bool:
        """Check if a country is enabled for operations."""
        country = await self.get_by_iso2(iso2)
        return country is not None and country.is_enabled and country.launch_status in ("ACTIVE", "BETA")

    async def get_timezone(self, iso2: str) -> Optional[str]:
        """Get the default timezone for a country code."""
        country = await self.get_by_iso2(iso2)
        return country.default_timezone if country else None

    async def get_currency(self, iso2: str) -> Optional[str]:
        """Get the default currency code for a country."""
        country = await self.get_by_iso2(iso2)
        return country.default_currency_code if country else None

    async def get_phone_code(self, iso2: str) -> Optional[str]:
        """Get the dial code for a country."""
        country = await self.get_by_iso2(iso2)
        return country.phone_country_code if country else None

    async def to_api_dict(self, country: Country) -> dict:
        """Serialize country to API response format."""
        return {
            "iso2": country.iso_alpha2,
            "iso3": country.iso_alpha3,
            "name": country.name,
            "native_name": country.native_name,
            "flag_emoji": country.flag_emoji,
            "currency": country.default_currency_code,
            "timezone": country.default_timezone,
            "languages": country.supported_language_codes,
            "phone_code": country.phone_country_code,
            "date_format": country.date_format,
            "is_rtl": country.is_rtl,
            "launch_status": country.launch_status,
            "is_enabled": country.is_enabled,
        }
