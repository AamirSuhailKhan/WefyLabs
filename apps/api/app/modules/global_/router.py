"""
Global Infrastructure API Router
==================================
Part 14 — Global Multi-Country Infrastructure & Localization Engine
Public API endpoints for country, market, currency, configuration, localization,
tax/fees, pipelines, phone, addresses, and provider health.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from decimal import Decimal
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.global_.countries.service import CountryService
from app.modules.global_.markets.service import MarketService, MarketActivationService
from app.modules.global_.currencies.exchange_rate_service import ExchangeRateService
from app.modules.global_.currencies.money import Money, FXUnavailableError
from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext
from app.modules.global_.property_schema.schema_registry import PropertySchemaRegistry, UnitConversionService
from app.modules.global_.ai_context.global_context_builder import GlobalContextBuilder
from app.modules.global_.monitoring.market_health_service import MarketHealthService
from app.modules.global_.phone.phone_service import PhoneService
from app.modules.global_.addresses.address_service import AddressService
from app.modules.global_.localization.translation_service import TranslationService
from app.modules.global_.pipelines.regional_pipeline_service import RegionalPipelineService
from app.modules.global_.feature_flags.market_flag_service import MarketFlagService
from app.modules.global_.tax.tax_fee_service import TaxFeeService
from app.modules.global_.analytics.cross_country_analytics import CrossCountryAnalyticsEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/global", tags=["Global Infrastructure"])


# ─────────────────────────────────────────────────────────────────────────────
# COUNTRIES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/countries", summary="List active countries")
async def list_countries(
    include_planned: bool = Query(False, description="Include countries in PLANNED status"),
    db: AsyncSession = Depends(get_db),
):
    """Return all enabled countries available on the platform."""
    service = CountryService(db)
    if include_planned:
        countries = await service.list_all()
    else:
        countries = await service.get_active_countries()

    return {
        "countries": [await service.to_api_dict(c) for c in countries],
        "total": len(countries),
    }


@router.get("/countries/{iso2}", summary="Get country detail")
async def get_country(iso2: str, db: AsyncSession = Depends(get_db)):
    """Get full country configuration by ISO Alpha-2 code."""
    service = CountryService(db)
    country = await service.get_by_iso2(iso2.upper())
    if not country:
        raise HTTPException(status_code=404, detail=f"Country '{iso2}' not found.")
    return await service.to_api_dict(country)


@router.get("/countries/{iso2}/markets", summary="Markets for a country")
async def get_country_markets(iso2: str, db: AsyncSession = Depends(get_db)):
    """Return all active markets within a country."""
    country_service = CountryService(db)
    country = await country_service.get_by_iso2(iso2.upper())
    if not country:
        raise HTTPException(status_code=404, detail=f"Country '{iso2}' not found.")

    market_service = MarketService(db)
    markets = await market_service.get_markets_for_country(str(country.id))
    return {
        "country": iso2.upper(),
        "markets": [await market_service.to_api_dict(m) for m in markets],
        "total": len(markets),
    }


# ─────────────────────────────────────────────────────────────────────────────
# MARKETS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/markets/{market_id}", summary="Get market detail")
async def get_market(market_id: str, db: AsyncSession = Depends(get_db)):
    service = MarketService(db)
    market = await service.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail=f"Market '{market_id}' not found.")
    return await service.to_api_dict(market)


@router.get("/markets/by-slug/{slug}", summary="Get market by slug")
async def get_market_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    service = MarketService(db)
    market = await service.get_by_slug(slug)
    if not market:
        raise HTTPException(status_code=404, detail=f"Market '{slug}' not found.")
    return await service.to_api_dict(market)


# ─────────────────────────────────────────────────────────────────────────────
# CURRENCIES & FX
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/exchange-rates", summary="Get current FX rates")
async def get_exchange_rates(
    base: str = Query("USD", description="Base currency ISO code"),
    quotes: Optional[str] = Query(None, description="Comma-separated quote currencies"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return current FX rates.
    Status FX_UNAVAILABLE is returned explicitly — never silent 1:1.
    """
    service = ExchangeRateService(db)
    quote_list = [q.strip().upper() for q in quotes.split(",")] if quotes else [
        "AED", "INR", "GBP", "SAR", "SGD", "AUD", "CAD", "QAR"
    ]

    rates = {}
    for quote in quote_list:
        result = await service.get_rate(base.upper(), quote)
        rates[quote] = {
            "rate": str(result.rate),
            "rate_type": result.rate_type,
            "provider": result.provider,
            "status": result.status,
            "valid_from": result.valid_from.isoformat(),
        }

    return {
        "base_currency": base.upper(),
        "rates": rates,
    }


@router.get("/exchange-rates/historical", summary="Get historical FX rate")
async def get_historical_fx(
    base: str = Query(..., description="Base currency"),
    quote: str = Query(..., description="Quote currency"),
    snapshot_date: date = Query(..., description="Date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """Get FX rate for a specific historical date (for financial reports)."""
    service = ExchangeRateService(db)
    result = await service.get_historical_rate(base.upper(), quote.upper(), snapshot_date)
    return {
        "base_currency": base.upper(),
        "quote_currency": quote.upper(),
        "rate": str(result.rate),
        "rate_type": result.rate_type,
        "provider": result.provider,
        "snapshot_date": str(snapshot_date),
        "status": result.status,
    }


@router.post("/convert", summary="Convert amount between currencies")
async def convert_currency(
    amount: str,
    from_currency: str,
    to_currency: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Convert a monetary amount between two currencies.
    Returns FX_UNAVAILABLE if no rate is available — never silent 1:1.
    """
    try:
        money = Money.of(amount, from_currency)
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=f"Invalid amount or currency: {e}")

    service = ExchangeRateService(db)
    try:
        result = await service.convert(money, to_currency)
        return {
            "original": money.to_dict(),
            "converted": result.converted.to_dict(),
            "rate": str(result.rate),
            "rate_type": result.rate_type,
            "provider": result.provider,
            "timestamp": result.timestamp,
            "status": result.status,
        }
    except FXUnavailableError as e:
        return {
            "status": "FX_UNAVAILABLE",
            "base_currency": from_currency.upper(),
            "quote_currency": to_currency.upper(),
            "message": str(e),
        }


# ─────────────────────────────────────────────────────────────────────────────
# TIMEZONE & LOCALIZATION
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/timezones/resolve", summary="Resolve effective timezone")
async def resolve_timezone(
    user_tz: Optional[str] = Query(None),
    org_tz: Optional[str] = Query(None),
    market_tz: Optional[str] = Query(None),
    country_tz: Optional[str] = Query(None),
):
    """Resolve effective timezone from context hierarchy."""
    context = TimezoneContext(
        user_timezone=user_tz,
        org_timezone=org_tz,
        market_timezone=market_tz,
        country_timezone=country_tz,
    )
    resolved = TimezoneService.resolve(context)
    return {"resolved_timezone": resolved}


@router.get("/translations/{locale}", summary="Get translations for locale namespace")
async def get_translations(
    locale: str,
    namespace: str = Query("common"),
    db: AsyncSession = Depends(get_db),
):
    """Return dictionary of translated strings for a locale namespace."""
    service = TranslationService(db)
    data = await service.get_namespace(namespace, locale)
    return {
        "locale": locale,
        "namespace": namespace,
        "translations": data,
        "is_rtl": TranslationService.is_rtl(locale),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PHONE & ADDRESSES
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/phone/validate", summary="Validate & Normalize Phone Number")
async def validate_phone(
    phone: str = Body(..., embed=True),
    default_region: Optional[str] = Body(None, embed=True),
):
    """Validates and normalizes phone number to E.164 with masking."""
    parsed = PhoneService.parse_phone(phone, default_region=default_region)
    return parsed.to_dict()


@router.post("/addresses/format", summary="Format Country Specific Address")
async def format_address(
    country_code: str = Body(..., embed=True),
    components: Dict[str, Any] = Body(..., embed=True),
):
    """Formats structured address components into canonical national format."""
    structured = AddressService.format_address(country_code, components)
    return structured.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# PROPERTY SCHEMA & UNITS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/property-schema", summary="Get property schema for market")
async def get_property_schema(
    market_id: Optional[str] = Query(None),
    country_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return the active property schema for a market or country."""
    registry = PropertySchemaRegistry(db)
    schema = await registry.get_schema(market_id=market_id, country_id=country_id)
    if not schema:
        return {"schema": None, "message": "No schema configured — all property types accepted."}

    return {
        "schema_id": str(schema.id),
        "name": schema.name,
        "version": schema.version,
        "property_type_codes": schema.property_type_codes,
        "area_units": schema.area_units,
    }


@router.get("/area-units/convert", summary="Convert area between units")
async def convert_area(
    value: float,
    from_unit: str = Query("sqft"),
    to_unit: str = Query("sqm"),
):
    """Convert area values between units (sqft, sqm, sqyd, marla, kanal)."""
    sqft_result = UnitConversionService.to_sqft(value, from_unit)
    converted = UnitConversionService.from_sqft(sqft_result.canonical_value, to_unit)
    return {
        "original_value": value,
        "original_unit": from_unit,
        "converted_value": converted,
        "converted_unit": to_unit,
        "sqft_canonical": sqft_result.canonical_value,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TAX & TRANSACTION COSTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/tax-fees/calculate", summary="Calculate Real Estate Transaction Costs")
async def calculate_transaction_costs(
    price: str = Body(...),
    currency: str = Body(...),
    country_code: str = Body(...),
    market_id: Optional[str] = Body(None),
    is_off_plan: bool = Body(False),
    is_first_home: bool = Body(False),
    buyer_is_resident: bool = Body(True),
):
    """Calculates all government, legal, and brokerage costs for a transaction."""
    money = Money.of(price, currency)
    breakdown = TaxFeeService.calculate_transaction_costs(
        purchase_price=money,
        country_code=country_code,
        market_id=market_id,
        is_off_plan=is_off_plan,
        is_first_home=is_first_home,
        buyer_is_resident=buyer_is_resident,
    )
    return breakdown.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# REGIONAL PIPELINES & FEATURE FLAGS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/pipelines/stages", summary="Get Pipeline Stages for Market")
async def get_pipeline_stages(
    market_id: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = RegionalPipelineService(db)
    stages = await service.get_pipeline_stages(market_id=market_id, organization_id=organization_id)
    return {
        "market_id": market_id,
        "stages": [
            {
                "stage_key": s.stage_key,
                "label": s.label,
                "sort_order": s.sort_order,
                "is_terminal": s.is_terminal,
                "is_won": s.is_won,
                "allowed_next_stages": s.allowed_next_stages,
            }
            for s in stages
        ]
    }


@router.get("/feature-flags", summary="Get effective market feature flags")
async def get_feature_flags(
    market_id: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = MarketFlagService(db)
    flags = await service.get_all_flags(market_id=market_id, organization_id=organization_id)
    return {"market_id": market_id, "organization_id": organization_id, "flags": flags}


# ─────────────────────────────────────────────────────────────────────────────
# CROSS-COUNTRY REVENUE ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analytics/revenue-consolidated", summary="Consolidated Multi-Market Revenue")
async def get_consolidated_revenue(
    organization_id: str = Query(...),
    target_currency: str = Query("USD"),
    db: AsyncSession = Depends(get_db),
):
    engine = CrossCountryAnalyticsEngine(db)
    report = await engine.generate_global_revenue_report(
        organization_id=organization_id,
        target_reporting_currency=target_currency,
    )
    return report.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# AI CONTEXT
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/ai-context", summary="Get AI context for a country/market")
async def get_ai_context(
    country_code: Optional[str] = Query(None),
    market_id: Optional[str] = Query(None),
    locale: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get the dynamic AI context that would be injected for a customer interaction."""
    builder = GlobalContextBuilder(db)
    context = await builder.build(
        country_code=country_code,
        market_id=market_id,
        locale=locale,
    )
    if not context:
        raise HTTPException(status_code=404, detail="Could not resolve country/market context.")

    return {
        "country_code": context.country_code,
        "country_name": context.country_name,
        "market_name": context.market_name,
        "currency_code": context.currency_code,
        "timezone": context.timezone,
        "language_code": context.language_code,
        "is_rtl": context.is_rtl,
        "date_format": context.date_format,
        "area_unit": context.area_unit,
        "property_types": context.property_types,
        "compliance_framework": context.compliance_framework,
        "ai_persona_hint": context.ai_persona_hint,
        "system_prompt_fragment": context.to_system_prompt_fragment(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM & MARKET HEALTH
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health", summary="Global platform health")
async def platform_health(
    market_id: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Full diagnostic health check for global infrastructure."""
    service = MarketHealthService(db)
    return await service.get_platform_health(market_id=market_id, country_code=country_code)
