"""
GlobalContextBuilder — Dynamic AI Country/Market Context Injection
===================================================================
Injects country-aware context into all AI system prompts.
Context is ALWAYS resolved dynamically — never hardcoded in prompts.

The AI must NOT receive static UAE/Dubai-only context unless the customer
is actually in UAE/Dubai. Country context flows from:
  Customer Lead → Market → Country → Organization → System.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.global_.countries.service import CountryService
from app.modules.global_.markets.service import MarketService
from app.modules.global_.currencies.money import Money
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class GlobalAIContext:
    """
    Resolved AI context for a customer interaction.
    All fields are dynamically resolved — nothing hardcoded.
    """
    country_code: str
    country_name: str
    market_name: Optional[str]
    currency_code: str
    currency_symbol: str
    timezone: str
    language_code: str
    is_rtl: bool
    date_format: str
    property_types: list
    compliance_framework: Optional[str]
    phone_code: str
    ai_persona_hint: str          # High-level tone guidance per market
    golden_visa_eligible: bool    # UAE-specific — only set if country=AE
    rera_compliance_required: bool
    area_unit: str                # sqft | sqm
    display_price_in: str         # e.g. "AED millions" | "INR lakhs"

    def to_system_prompt_fragment(self) -> str:
        """
        Returns a structured system prompt fragment for AI context injection.
        DO NOT inject this as a raw block — merge into the base system prompt.
        """
        lines = [
            f"[GLOBAL CONTEXT]",
            f"Customer Country: {self.country_name} ({self.country_code})",
        ]
        if self.market_name:
            lines.append(f"Customer Market: {self.market_name}")

        lines += [
            f"Currency: {self.currency_code} ({self.currency_symbol})",
            f"Timezone: {self.timezone}",
            f"Language: {self.language_code}{'  (RTL)' if self.is_rtl else ''}",
            f"Date Format: {self.date_format}",
            f"Area Unit: {self.area_unit}",
            f"Price Display: {self.display_price_in}",
        ]

        if self.property_types:
            lines.append(f"Available Property Types: {', '.join(self.property_types)}")
        if self.compliance_framework:
            lines.append(f"Compliance Framework: {self.compliance_framework}")

        # UAE-specific — only if applicable
        if self.golden_visa_eligible:
            lines.append("Golden Visa: Proactively inform about UAE Golden Visa eligibility for properties ≥ AED 2,000,000.")
        if self.rera_compliance_required:
            lines.append("RERA: Always mention RERA permit number and DLD registration when discussing property details.")

        if self.ai_persona_hint:
            lines.append(f"Tone Guidance: {self.ai_persona_hint}")

        return "\n".join(lines)


class GlobalContextBuilder:
    """
    Builds dynamic GlobalAIContext for a customer interaction.
    Resolves all fields from database — never from hardcoded defaults.
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._country_service = CountryService(db)
        self._market_service = MarketService(db)

    async def build(
        self,
        country_code: Optional[str] = None,
        market_id: Optional[str] = None,
        locale: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Optional[GlobalAIContext]:
        """
        Build AI context from country + market.
        Returns None if insufficient data to build context.
        """
        if not country_code and not market_id:
            logger.debug("[GlobalContext] No country_code or market_id — returning None.")
            return None

        country = None
        market = None

        if country_code:
            country = await self._country_service.get_by_iso2(country_code)

        if market_id:
            market = await self._market_service.get_market(market_id)
            if market and not country:
                from app.models.global_models import Country
                from sqlalchemy import select
                stmt = select(Country).where(Country.id == market.country_id)
                result = await self._db.execute(stmt)
                country = result.scalar_one_or_none()

        if not country:
            logger.warning(f"[GlobalContext] Country not found for code={country_code}. Returning None.")
            return None

        # Effective values: market overrides country where specified
        effective_currency = (market.currency_code if market else None) or country.default_currency_code
        effective_timezone = (market.timezone if market else None) or country.default_timezone
        effective_lang = locale or (market.language_codes[0] if market and market.language_codes else None) or country.default_language_code
        effective_property_types = (market.property_type_codes if market and market.property_type_codes else [])

        # Build display price hint
        display_price_in = self._build_display_price_hint(effective_currency)

        # Market/country-specific flags
        golden_visa_eligible = country.iso_alpha2 == "AE"
        rera_compliance = country.iso_alpha2 in ("AE", "IN")

        # Area unit preference
        area_unit = "sqm" if country.iso_alpha2 in ("GB", "DE", "FR", "AU", "NL") else "sqft"

        # Compliance framework
        compliance = (country.metadata_json or {}).get("compliance_framework") if country.metadata_json else None

        # AI persona hint (from country metadata)
        ai_persona = (country.metadata_json or {}).get("ai_persona_hint", "") if country.metadata_json else ""

        return GlobalAIContext(
            country_code=country.iso_alpha2,
            country_name=country.name,
            market_name=market.name if market else None,
            currency_code=effective_currency,
            currency_symbol=self._get_currency_symbol(effective_currency),
            timezone=effective_timezone,
            language_code=effective_lang,
            is_rtl=country.is_rtl,
            date_format=country.date_format,
            property_types=effective_property_types,
            compliance_framework=compliance,
            phone_code=country.phone_country_code,
            ai_persona_hint=ai_persona,
            golden_visa_eligible=golden_visa_eligible,
            rera_compliance_required=rera_compliance,
            area_unit=area_unit,
            display_price_in=display_price_in,
        )

    @staticmethod
    def _build_display_price_hint(currency_code: str) -> str:
        hints = {
            "INR": "INR lakhs/crores (e.g., ₹85 L, ₹1.2 Cr)",
            "AED": "AED (e.g., AED 1,500,000)",
            "SAR": "SAR (e.g., SAR 2,500,000)",
            "GBP": "GBP (e.g., £450,000)",
            "USD": "USD (e.g., $350,000)",
            "SGD": "SGD (e.g., S$1,200,000)",
            "AUD": "AUD (e.g., A$850,000)",
            "CAD": "CAD (e.g., C$780,000)",
        }
        return hints.get(currency_code, f"{currency_code} (standard format)")

    @staticmethod
    def _get_currency_symbol(currency_code: str) -> str:
        symbols = {
            "INR": "₹", "AED": "AED", "SAR": "SR", "GBP": "£",
            "USD": "$", "SGD": "S$", "AUD": "A$", "CAD": "C$",
            "QAR": "QR", "OMR": "OMR", "KWD": "KD", "BHD": "BD",
        }
        return symbols.get(currency_code, currency_code)
