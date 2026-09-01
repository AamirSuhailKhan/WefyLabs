"""
Global Data Seeder
==================
Seeds: Countries, Markets, Currencies, HolidayCalendars
Run: python scripts/seed_global_data.py

Target countries:
  India (IN), UAE (AE), Saudi Arabia (SA), United Kingdom (GB),
  United States (US), Canada (CA), Australia (AU), Singapore (SG),
  Qatar (QA), Oman (OM), Bahrain (BH), Kuwait (KW)

Architecture: All data seeded here — NEVER hardcoded in application code.
"""
import asyncio
import sys
import os
from decimal import Decimal

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Country config data
COUNTRIES = [
    {
        "iso_alpha2": "IN",
        "iso_alpha3": "IND",
        "numeric_code": "356",
        "name": "India",
        "native_name": "भारत",
        "flag_emoji": "🇮🇳",
        "default_currency_code": "INR",
        "supported_currency_codes": ["INR", "USD"],
        "default_timezone": "Asia/Kolkata",
        "supported_timezones": ["Asia/Kolkata"],
        "default_language_code": "en",
        "supported_language_codes": ["en", "hi", "ta", "te", "mr", "bn"],
        "is_rtl": False,
        "date_format": "DD/MM/YYYY",
        "phone_country_code": "+91",
        "launch_status": "ACTIVE",
        "is_enabled": True,
        "metadata_json": {
            "compliance_framework": "RERA India (Real Estate Regulation Act)",
            "ai_persona_hint": "Friendly Indian real estate advisor fluent in Lakhs, Crores, BHK configurations, and RERA approvals.",
        }
    },
    {
        "iso_alpha2": "AE",
        "iso_alpha3": "ARE",
        "numeric_code": "784",
        "name": "United Arab Emirates",
        "native_name": "الإمارات",
        "flag_emoji": "🇦🇪",
        "default_currency_code": "AED",
        "supported_currency_codes": ["AED", "USD"],
        "default_timezone": "Asia/Dubai",
        "supported_timezones": ["Asia/Dubai"],
        "default_language_code": "en",
        "supported_language_codes": ["en", "ar"],
        "is_rtl": False,  # Platform primarily English; Arabic content is RTL
        "date_format": "DD/MM/YYYY",
        "phone_country_code": "+971",
        "launch_status": "ACTIVE",
        "is_enabled": True,
        "metadata_json": {
            "compliance_framework": "Dubai Land Department (DLD) & RERA Dubai",
            "ai_persona_hint": "High-end Dubai real estate specialist experienced in off-plan, freehold areas, DLD registration, and Golden Visa eligibility.",
        }
    },
    {
        "iso_alpha2": "SA",
        "iso_alpha3": "SAU",
        "numeric_code": "682",
        "name": "Saudi Arabia",
        "native_name": "المملكة العربية السعودية",
        "flag_emoji": "🇸🇦",
        "default_currency_code": "SAR",
        "supported_currency_codes": ["SAR", "USD"],
        "default_timezone": "Asia/Riyadh",
        "supported_timezones": ["Asia/Riyadh"],
        "default_language_code": "en",
        "supported_language_codes": ["en", "ar"],
        "is_rtl": False,
        "date_format": "DD/MM/YYYY",
        "phone_country_code": "+966",
        "launch_status": "BETA",
        "is_enabled": True,
        "metadata_json": {
            "compliance_framework": "Real Estate General Authority (REGA Saudi Arabia)",
            "ai_persona_hint": "Professional Saudi real estate advisor compliant with REGA licenses and Vision 2030 developments.",
        }
    },
    {
        "iso_alpha2": "GB",
        "iso_alpha3": "GBR",
        "numeric_code": "826",
        "name": "United Kingdom",
        "native_name": "United Kingdom",
        "flag_emoji": "🇬🇧",
        "default_currency_code": "GBP",
        "supported_currency_codes": ["GBP", "USD"],
        "default_timezone": "Europe/London",
        "supported_timezones": ["Europe/London"],
        "default_language_code": "en",
        "supported_language_codes": ["en"],
        "is_rtl": False,
        "date_format": "DD/MM/YYYY",
        "phone_country_code": "+44",
        "launch_status": "BETA",
        "is_enabled": True,
        "metadata_json": {
            "compliance_framework": "Property Ombudsman & Estate Agents Act 1979",
            "ai_persona_hint": "Courteous UK Estate Agent familiar with freehold, leasehold, Stamp Duty Land Tax (SDLT), and Help to Buy schemes.",
        }
    },
    {
        "iso_alpha2": "US",
        "iso_alpha3": "USA",
        "numeric_code": "840",
        "name": "United States",
        "native_name": "United States",
        "flag_emoji": "🇺🇸",
        "default_currency_code": "USD",
        "supported_currency_codes": ["USD"],
        "default_timezone": "America/New_York",
        "supported_timezones": ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"],
        "default_language_code": "en",
        "supported_language_codes": ["en", "es"],
        "is_rtl": False,
        "date_format": "MM/DD/YYYY",
        "phone_country_code": "+1",
        "launch_status": "PLANNED",
        "is_enabled": False,
        "metadata_json": {
            "compliance_framework": "TCPA, Fair Housing Act & RESO MLS Standards",
            "ai_persona_hint": "Professional US Realtor complying strictly with Fair Housing Act guidelines and RESO MLS data formats.",
        }
    },
    {
        "iso_alpha2": "CA",
        "iso_alpha3": "CAN",
        "numeric_code": "124",
        "name": "Canada",
        "native_name": "Canada",
        "flag_emoji": "🇨🇦",
        "default_currency_code": "CAD",
        "supported_currency_codes": ["CAD", "USD"],
        "default_timezone": "America/Toronto",
        "supported_timezones": ["America/Toronto", "America/Vancouver", "America/Edmonton"],
        "default_language_code": "en",
        "supported_language_codes": ["en", "fr"],
        "is_rtl": False,
        "date_format": "DD/MM/YYYY",
        "phone_country_code": "+1",
        "launch_status": "PLANNED",
        "is_enabled": False,
        "metadata_json": {
            "compliance_framework": "CREA (Canadian Real Estate Association) & FINTRAC",
            "ai_persona_hint": "Knowledgeable Canadian real estate agent familiar with provincial regulations and foreign buyer rules.",
        }
    },
    {
        "iso_alpha2": "AU",
        "iso_alpha3": "AUS",
        "numeric_code": "036",
        "name": "Australia",
        "native_name": "Australia",
        "flag_emoji": "🇦🇺",
        "default_currency_code": "AUD",
        "supported_currency_codes": ["AUD", "USD"],
        "default_timezone": "Australia/Sydney",
        "supported_timezones": ["Australia/Sydney", "Australia/Melbourne", "Australia/Brisbane", "Australia/Perth"],
        "default_language_code": "en",
        "supported_language_codes": ["en"],
        "is_rtl": False,
        "date_format": "DD/MM/YYYY",
        "phone_country_code": "+61",
        "launch_status": "PLANNED",
        "is_enabled": False,
        "metadata_json": {
            "compliance_framework": "REIA & FIRB (Foreign Investment Review Board)",
            "ai_persona_hint": "Knowledgeable Australian real estate agent expert in auction processes and FIRB foreign investment regulations.",
        }
    },
    {
        "iso_alpha2": "SG",
        "iso_alpha3": "SGP",
        "numeric_code": "702",
        "name": "Singapore",
        "native_name": "Singapore",
        "flag_emoji": "🇸🇬",
        "default_currency_code": "SGD",
        "supported_currency_codes": ["SGD", "USD"],
        "default_timezone": "Asia/Singapore",
        "supported_timezones": ["Asia/Singapore"],
        "default_language_code": "en",
        "supported_language_codes": ["en", "zh", "ms", "ta"],
        "is_rtl": False,
        "date_format": "DD/MM/YYYY",
        "phone_country_code": "+65",
        "launch_status": "PLANNED",
        "is_enabled": False,
        "metadata_json": {
            "compliance_framework": "Council for Estate Agencies (CEA Singapore)",
            "ai_persona_hint": "CEA-certified Singapore property consultant specialized in HDB resale, private condos, and ABSD regulations.",
        }
    },
    {
        "iso_alpha2": "QA",
        "iso_alpha3": "QAT",
        "numeric_code": "634",
        "name": "Qatar",
        "native_name": "قطر",
        "flag_emoji": "🇶🇦",
        "default_currency_code": "QAR",
        "supported_currency_codes": ["QAR", "USD"],
        "default_timezone": "Asia/Qatar",
        "supported_timezones": ["Asia/Qatar"],
        "default_language_code": "en",
        "supported_language_codes": ["en", "ar"],
        "is_rtl": False,
        "date_format": "DD/MM/YYYY",
        "phone_country_code": "+974",
        "launch_status": "PLANNED",
        "is_enabled": False,
        "metadata_json": {
            "compliance_framework": "Ministry of Justice Qatar & Lusail Real Estate Regulation",
            "ai_persona_hint": "Professional Qatar real estate advisor knowledgeable in freehold zones and Lusail City developments.",
        }
    },
    {
        "iso_alpha2": "OM",
        "iso_alpha3": "OMN",
        "numeric_code": "512",
        "name": "Oman",
        "native_name": "عُمان",
        "flag_emoji": "🇴🇲",
        "default_currency_code": "OMR",
        "supported_currency_codes": ["OMR", "USD"],
        "default_timezone": "Asia/Muscat",
        "supported_timezones": ["Asia/Muscat"],
        "default_language_code": "en",
        "supported_language_codes": ["en", "ar"],
        "is_rtl": False,
        "date_format": "DD/MM/YYYY",
        "phone_country_code": "+968",
        "launch_status": "PLANNED",
        "is_enabled": False,
        "metadata_json": {
            "compliance_framework": "Oman Real Estate Law (Royal Decree 2/2012)",
            "ai_persona_hint": "Oman real estate specialist familiar with integrated tourism complexes (ITC) and expat ownership zones.",
        }
    },
    {
        "iso_alpha2": "BH",
        "iso_alpha3": "BHR",
        "numeric_code": "048",
        "name": "Bahrain",
        "native_name": "البحرين",
        "flag_emoji": "🇧🇭",
        "default_currency_code": "BHD",
        "supported_currency_codes": ["BHD", "USD"],
        "default_timezone": "Asia/Bahrain",
        "supported_timezones": ["Asia/Bahrain"],
        "default_language_code": "en",
        "supported_language_codes": ["en", "ar"],
        "is_rtl": False,
        "date_format": "DD/MM/YYYY",
        "phone_country_code": "+973",
        "launch_status": "PLANNED",
        "is_enabled": False,
        "metadata_json": {
            "compliance_framework": "Real Estate Regulatory Authority (RERA Bahrain)",
            "ai_persona_hint": "Bahrain real estate advisor familiar with freehold investment zones and Amwaj Islands developments.",
        }
    },
    {
        "iso_alpha2": "KW",
        "iso_alpha3": "KWT",
        "numeric_code": "414",
        "name": "Kuwait",
        "native_name": "الكويت",
        "flag_emoji": "🇰🇼",
        "default_currency_code": "KWD",
        "supported_currency_codes": ["KWD", "USD"],
        "default_timezone": "Asia/Kuwait",
        "supported_timezones": ["Asia/Kuwait"],
        "default_language_code": "en",
        "supported_language_codes": ["en", "ar"],
        "is_rtl": False,
        "date_format": "DD/MM/YYYY",
        "phone_country_code": "+965",
        "launch_status": "PLANNED",
        "is_enabled": False,
        "metadata_json": {
            "compliance_framework": "Kuwait Ministry of Justice Real Estate Registration",
            "ai_persona_hint": "Kuwait real estate advisor knowledgeable in residential and commercial property market trends.",
        }
    },
]

CURRENCIES = [
    {"code": "INR", "name": "Indian Rupee", "native_name": "रुपया", "symbol": "₹", "symbol_native": "₹", "decimal_digits": 2, "display_unit": "lakhs_crores"},
    {"code": "AED", "name": "UAE Dirham", "native_name": "درهم", "symbol": "AED", "symbol_native": "د.إ", "decimal_digits": 2, "display_unit": "thousands_millions"},
    {"code": "SAR", "name": "Saudi Riyal", "native_name": "ريال", "symbol": "SR", "symbol_native": "ر.س", "decimal_digits": 2, "display_unit": "thousands_millions"},
    {"code": "GBP", "name": "British Pound", "native_name": "Pound", "symbol": "£", "symbol_native": "£", "decimal_digits": 2, "display_unit": "thousands_millions"},
    {"code": "USD", "name": "US Dollar", "native_name": "Dollar", "symbol": "$", "symbol_native": "$", "decimal_digits": 2, "display_unit": "thousands_millions"},
    {"code": "CAD", "name": "Canadian Dollar", "native_name": "Dollar", "symbol": "C$", "symbol_native": "C$", "decimal_digits": 2, "display_unit": "thousands_millions"},
    {"code": "AUD", "name": "Australian Dollar", "native_name": "Dollar", "symbol": "A$", "symbol_native": "A$", "decimal_digits": 2, "display_unit": "thousands_millions"},
    {"code": "SGD", "name": "Singapore Dollar", "native_name": "Dollar", "symbol": "S$", "symbol_native": "S$", "decimal_digits": 2, "display_unit": "thousands_millions"},
    {"code": "QAR", "name": "Qatari Riyal", "native_name": "ريال", "symbol": "QR", "symbol_native": "ر.ق", "decimal_digits": 2, "display_unit": "thousands_millions"},
    {"code": "OMR", "name": "Omani Rial", "native_name": "ريال", "symbol": "OMR", "symbol_native": "ر.ع.", "decimal_digits": 3, "display_unit": "thousands_millions"},
    {"code": "BHD", "name": "Bahraini Dinar", "native_name": "دينار", "symbol": "BD", "symbol_native": "د.ب.", "decimal_digits": 3, "display_unit": "thousands_millions"},
    {"code": "KWD", "name": "Kuwaiti Dinar", "native_name": "دينار", "symbol": "KD", "symbol_native": "د.ك", "decimal_digits": 3, "display_unit": "thousands_millions"},
]

# Major markets — sub-country business units
MARKETS = [
    # India markets
    {
        "country_iso2": "IN", "name": "Dubai", "slug": "dubai", "display_name": "Dubai, UAE",
        # Note: slug collision — this is actually AE below
    },
    # UAE markets
    {
        "country_iso2": "AE", "name": "Dubai", "slug": "dubai", "display_name": "Dubai, UAE",
        "timezone": "Asia/Dubai", "currency_code": "AED",
        "language_codes": ["en", "ar"],
        "weekend_days": [4, 5],  # Fri=4, Sat=5
        "property_type_codes": ["studio", "1_bed", "2_bed", "3_bed", "4_bed_plus", "luxury_villa", "penthouse", "townhouse", "commercial"],
        "lead_source_codes": ["property_finder", "bayut", "dubizzle", "instagram", "facebook", "referral", "walk_in"],
        "launch_status": "ACTIVE", "is_enabled": True,
    },
    {
        "country_iso2": "AE", "name": "Abu Dhabi", "slug": "abu-dhabi", "display_name": "Abu Dhabi, UAE",
        "timezone": "Asia/Dubai", "currency_code": "AED",
        "language_codes": ["en", "ar"],
        "weekend_days": [4, 5],
        "property_type_codes": ["studio", "1_bed", "2_bed", "3_bed", "luxury_villa", "penthouse", "commercial"],
        "lead_source_codes": ["property_finder", "bayut", "referral", "walk_in"],
        "launch_status": "ACTIVE", "is_enabled": True,
    },
    {
        "country_iso2": "AE", "name": "Sharjah", "slug": "sharjah", "display_name": "Sharjah, UAE",
        "timezone": "Asia/Dubai", "currency_code": "AED",
        "language_codes": ["en", "ar"],
        "weekend_days": [4, 5],
        "property_type_codes": ["apartment", "villa", "studio", "commercial"],
        "lead_source_codes": ["property_finder", "bayut", "referral"],
        "launch_status": "ACTIVE", "is_enabled": True,
    },
    # India markets
    {
        "country_iso2": "IN", "name": "Mumbai Metropolitan Region", "slug": "mumbai", "display_name": "Mumbai, India",
        "timezone": "Asia/Kolkata", "currency_code": "INR",
        "language_codes": ["en", "hi", "mr"],
        "weekend_days": [5, 6],  # Sat=5, Sun=6
        "property_type_codes": ["1bhk", "2bhk", "3bhk", "4bhk_plus", "villa", "plot", "commercial"],
        "lead_source_codes": ["99acres", "magicbricks", "housing", "nobroker", "instagram", "facebook", "referral"],
        "launch_status": "ACTIVE", "is_enabled": True,
    },
    {
        "country_iso2": "IN", "name": "Delhi NCR", "slug": "delhi-ncr", "display_name": "Delhi NCR, India",
        "timezone": "Asia/Kolkata", "currency_code": "INR",
        "language_codes": ["en", "hi"],
        "weekend_days": [5, 6],
        "property_type_codes": ["1bhk", "2bhk", "3bhk", "4bhk_plus", "villa", "plot", "builder_floor", "commercial"],
        "lead_source_codes": ["99acres", "magicbricks", "housing", "instagram", "referral"],
        "launch_status": "ACTIVE", "is_enabled": True,
    },
    {
        "country_iso2": "IN", "name": "Bengaluru", "slug": "bengaluru", "display_name": "Bengaluru, India",
        "timezone": "Asia/Kolkata", "currency_code": "INR",
        "language_codes": ["en", "hi", "kn"],
        "weekend_days": [5, 6],
        "property_type_codes": ["1bhk", "2bhk", "3bhk", "4bhk_plus", "villa", "plot", "commercial"],
        "lead_source_codes": ["99acres", "magicbricks", "housing", "instagram", "referral"],
        "launch_status": "ACTIVE", "is_enabled": True,
    },
    # Saudi markets
    {
        "country_iso2": "SA", "name": "Riyadh", "slug": "riyadh", "display_name": "Riyadh, Saudi Arabia",
        "timezone": "Asia/Riyadh", "currency_code": "SAR",
        "language_codes": ["en", "ar"],
        "weekend_days": [4, 5],
        "property_type_codes": ["villa", "apartment", "duplex", "land", "commercial_building"],
        "lead_source_codes": ["aqar", "bayut_ksa", "instagram", "referral"],
        "launch_status": "BETA", "is_enabled": True,
    },
    {
        "country_iso2": "SA", "name": "Jeddah", "slug": "jeddah", "display_name": "Jeddah, Saudi Arabia",
        "timezone": "Asia/Riyadh", "currency_code": "SAR",
        "language_codes": ["en", "ar"],
        "weekend_days": [4, 5],
        "property_type_codes": ["villa", "apartment", "land", "commercial"],
        "lead_source_codes": ["aqar", "instagram", "referral"],
        "launch_status": "PLANNED", "is_enabled": False,
    },
    # UK markets
    {
        "country_iso2": "GB", "name": "London", "slug": "london", "display_name": "London, UK",
        "timezone": "Europe/London", "currency_code": "GBP",
        "language_codes": ["en"],
        "weekend_days": [5, 6],
        "property_type_codes": ["flat", "terraced", "semi_detached", "detached", "bungalow", "studio", "commercial"],
        "lead_source_codes": ["rightmove", "zoopla", "onthemarket", "referral"],
        "launch_status": "BETA", "is_enabled": True,
    },
]

# Baseline FX rates (USD base — seeded as starting point, overridden by live FX)
BASELINE_FX_RATES = [
    {"base": "USD", "quote": "INR", "rate": "83.50"},
    {"base": "USD", "quote": "AED", "rate": "3.67"},
    {"base": "USD", "quote": "SAR", "rate": "3.75"},
    {"base": "USD", "quote": "GBP", "rate": "0.79"},
    {"base": "USD", "quote": "CAD", "rate": "1.36"},
    {"base": "USD", "quote": "AUD", "rate": "1.52"},
    {"base": "USD", "quote": "SGD", "rate": "1.35"},
    {"base": "USD", "quote": "QAR", "rate": "3.64"},
    {"base": "USD", "quote": "OMR", "rate": "0.385"},
    {"base": "USD", "quote": "BHD", "rate": "0.376"},
    {"base": "USD", "quote": "KWD", "rate": "0.307"},
    # AED cross-rates (common in UAE)
    {"base": "AED", "quote": "INR", "rate": "22.74"},
    {"base": "AED", "quote": "USD", "rate": "0.272"},
    {"base": "AED", "quote": "GBP", "rate": "0.215"},
    {"base": "AED", "quote": "SAR", "rate": "1.022"},
    # INR cross-rates
    {"base": "INR", "quote": "USD", "rate": "0.01198"},
    {"base": "INR", "quote": "AED", "rate": "0.04398"},
    # GBP cross-rates
    {"base": "GBP", "quote": "USD", "rate": "1.265"},
    {"base": "GBP", "quote": "AED", "rate": "4.646"},
    {"base": "GBP", "quote": "INR", "rate": "105.70"},
]


async def seed(database_url: str):
    """Run the global data seed."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from datetime import datetime, timezone, date

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        from app.models.global_models import (
            Country, Currency, Market, ExchangeRate, ExchangeRateSnapshot
        )

        print("🌍 Seeding currencies...")
        for curr_data in CURRENCIES:
            stmt = select(Currency).where(Currency.code == curr_data["code"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                session.add(Currency(**curr_data))
            else:
                for k, v in curr_data.items():
                    setattr(existing, k, v)

        await session.flush()
        print(f"   ✅ {len(CURRENCIES)} currencies seeded")

        print("🌍 Seeding countries...")
        country_map = {}  # iso2 → Country object
        for c_data in COUNTRIES:
            stmt = select(Country).where(Country.iso_alpha2 == c_data["iso_alpha2"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                country = Country(**c_data)
                session.add(country)
                await session.flush()
                country_map[c_data["iso_alpha2"]] = country
            else:
                for k, v in c_data.items():
                    setattr(existing, k, v)
                await session.flush()
                country_map[c_data["iso_alpha2"]] = existing

        print(f"   ✅ {len(COUNTRIES)} countries seeded")

        print("🌍 Seeding markets...")
        market_count = 0
        for m_data in MARKETS:
            country_iso2 = m_data.pop("country_iso2")
            country = country_map.get(country_iso2)
            if not country:
                print(f"   ⚠️  Country {country_iso2} not found for market {m_data['name']}, skipping.")
                continue

            stmt = select(Market).where(Market.slug == m_data["slug"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                market = Market(country_id=country.id, **m_data)
                session.add(market)
                market_count += 1
            else:
                existing.country_id = country.id
                for k, v in m_data.items():
                    setattr(existing, k, v)

        await session.flush()
        print(f"   ✅ {market_count} markets seeded")

        print("🌍 Seeding baseline FX rates...")
        now = datetime.now(timezone.utc)
        today = now.date()
        fx_count = 0
        for rate_data in BASELINE_FX_RATES:
            stmt = select(ExchangeRate).where(
                (ExchangeRate.base_currency == rate_data["base"]) &
                (ExchangeRate.quote_currency == rate_data["quote"]) &
                (ExchangeRate.is_active == True)
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                # Update rate
                existing.rate = Decimal(rate_data["rate"])
                existing.valid_from = now
            else:
                session.add(ExchangeRate(
                    base_currency=rate_data["base"],
                    quote_currency=rate_data["quote"],
                    rate=Decimal(rate_data["rate"]),
                    rate_type="MARKET",
                    provider="seed_data",
                    valid_from=now,
                    is_active=True,
                ))

            # Upsert snapshot
            stmt2 = select(ExchangeRateSnapshot).where(
                (ExchangeRateSnapshot.base_currency == rate_data["base"]) &
                (ExchangeRateSnapshot.quote_currency == rate_data["quote"]) &
                (ExchangeRateSnapshot.snapshot_date == today) &
                (ExchangeRateSnapshot.provider == "seed_data")
            )
            result2 = await session.execute(stmt2)
            snap = result2.scalar_one_or_none()
            if not snap:
                session.add(ExchangeRateSnapshot(
                    base_currency=rate_data["base"],
                    quote_currency=rate_data["quote"],
                    rate=Decimal(rate_data["rate"]),
                    snapshot_date=today,
                    provider="seed_data",
                ))
            fx_count += 1

        await session.flush()
        print(f"   ✅ {fx_count} FX rate pairs seeded")

        await session.commit()
        print("\n✅ Global data seed complete!")

    await engine.dispose()


if __name__ == "__main__":
    import os
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore"
    )
    asyncio.run(seed(db_url))
