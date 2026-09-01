from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class CurrencyPack(BaseModel):
    code: str  # INR, USD, AED, GBP, EUR, AUD, SGD, SAR
    symbol: str  # ₹, $, AED, £, €, A$, S$, SR
    display_unit: str  # lakhs_crores, thousands_millions, millions
    exchange_rate_to_usd: float  # Baseline exchange rate

class CountryPack(BaseModel):
    country_code: str  # ISO 2-letter code (IN, US, AE, UK, CA, AU, SG, SA)
    country_name: str
    flag_emoji: str
    currency: CurrencyPack
    primary_messaging_channel: str  # whatsapp | sms | email
    compliance_framework: str
    tax_name: str
    default_tax_rate_pct: float
    property_types: List[str]
    major_portals: List[str]
    payment_gateway: str  # razorpay | stripe | tap
    phone_code: str
    phone_regex: str
    date_format: str  # DD/MM/YYYY vs MM/DD/YYYY
    ai_system_persona: str

class InternationalFrameworkRegistry:
    """
    Configuration-driven Global Real Estate Engine supporting 100+ countries.
    Zero country-specific code inside core business logic.
    """

    _REGISTRY: Dict[str, CountryPack] = {
        "IN": CountryPack(
            country_code="IN",
            country_name="India",
            flag_emoji="🇮🇳",
            currency=CurrencyPack(code="INR", symbol="₹", display_unit="lakhs_crores", exchange_rate_to_usd=83.5),
            primary_messaging_channel="whatsapp",
            compliance_framework="RERA India (Real Estate Regulation Act)",
            tax_name="GST",
            default_tax_rate_pct=18.0,
            property_types=["1bhk", "2bhk", "3bhk", "4bhk_plus", "villa", "plot", "commercial"],
            major_portals=["99acres", "MagicBricks", "Housing.com", "NoBroker"],
            payment_gateway="razorpay",
            phone_code="+91",
            phone_regex=r"^(\+91)?([6-9]\d{9})$",
            date_format="DD/MM/YYYY",
            ai_system_persona="Friendly Indian real estate advisor fluent in Lakhs, Crores, BHK configurations, and RERA approvals."
        ),
        "AE": CountryPack(
            country_code="AE",
            country_name="United Arab Emirates",
            flag_emoji="🇦🇪",
            currency=CurrencyPack(code="AED", symbol="AED", display_unit="thousands_millions", exchange_rate_to_usd=3.67),
            primary_messaging_channel="whatsapp",
            compliance_framework="Dubai Land Department (DLD) & RERA Dubai",
            tax_name="VAT",
            default_tax_rate_pct=5.0,
            property_types=["studio", "1_bed", "2_bed", "3_bed", "luxury_villa", "penthouse", "commercial"],
            major_portals=["Property Finder", "Bayut", "Dubizzle"],
            payment_gateway="stripe",
            phone_code="+971",
            phone_regex=r"^(\+971)?([5]\d{8})$",
            date_format="DD/MM/YYYY",
            ai_system_persona="High-end Dubai real estate specialist experienced in off-plan, freehold areas, and DLD registration."
        ),
        "US": CountryPack(
            country_code="US",
            country_name="United States",
            flag_emoji="🇺🇸",
            currency=CurrencyPack(code="USD", symbol="$", display_unit="thousands_millions", exchange_rate_to_usd=1.0),
            primary_messaging_channel="sms",
            compliance_framework="TCPA, Fair Housing Act & RESO MLS Standards",
            tax_name="Sales Tax",
            default_tax_rate_pct=0.0,
            property_types=["single_family", "condo", "townhouse", "multi_family", "land", "commercial"],
            major_portals=["Zillow", "Realtor.com", "Redfin", "Trulia"],
            payment_gateway="stripe",
            phone_code="+1",
            phone_regex=r"^(\+1)?([2-9]\d{9})$",
            date_format="MM/DD/YYYY",
            ai_system_persona="Professional US Realtor complying strictly with Fair Housing Act guidelines and RESO MLS formats."
        ),
        "UK": CountryPack(
            country_code="UK",
            country_name="United Kingdom",
            flag_emoji="🇬🇧",
            currency=CurrencyPack(code="GBP", symbol="£", display_unit="thousands_millions", exchange_rate_to_usd=0.79),
            primary_messaging_channel="email",
            compliance_framework="Property Ombudsman & Estate Agents Act 1979",
            tax_name="VAT",
            default_tax_rate_pct=20.0,
            property_types=["flat", "terraced", "semi_detached", "detached", "bungalow"],
            major_portals=["Rightmove", "Zoopla", "OnTheMarket"],
            payment_gateway="stripe",
            phone_code="+44",
            phone_regex=r"^(\+44)?(7\d{9})$",
            date_format="DD/MM/YYYY",
            ai_system_persona="Courteous UK Estate Agent familiar with freehold, leasehold, and Stamp Duty Land Tax (SDLT)."
        ),
        "AU": CountryPack(
            country_code="AU",
            country_name="Australia",
            flag_emoji="🇦🇺",
            currency=CurrencyPack(code="AUD", symbol="A$", display_unit="thousands_millions", exchange_rate_to_usd=1.52),
            primary_messaging_channel="sms",
            compliance_framework="REIA & FIRB (Foreign Investment Review Board)",
            tax_name="GST",
            default_tax_rate_pct=10.0,
            property_types=["house", "unit", "apartment", "townhouse", "acreage"],
            major_portals=["Realestate.com.au (REA Group)", "Domain"],
            payment_gateway="stripe",
            phone_code="+61",
            phone_regex=r"^(\+61)?(4\d{8})$",
            date_format="DD/MM/YYYY",
            ai_system_persona="Knowledgeable Australian real estate agent expert in auction processes and FIRB regulations."
        ),
        "SG": CountryPack(
            country_code="SG",
            country_name="Singapore",
            flag_emoji="🇸🇬",
            currency=CurrencyPack(code="SGD", symbol="S$", display_unit="thousands_millions", exchange_rate_to_usd=1.35),
            primary_messaging_channel="whatsapp",
            compliance_framework="Council for Estate Agencies (CEA Singapore)",
            tax_name="GST",
            default_tax_rate_pct=9.0,
            property_types=["hdb_flat", "condo", "landed_house", "executive_condo"],
            major_portals=["PropertyGuru Singapore", "99.co"],
            payment_gateway="stripe",
            phone_code="+65",
            phone_regex=r"^(\+65)?([89]\d{7})$",
            date_format="DD/MM/YYYY",
            ai_system_persona="CEA-certified Singapore property consultant specialized in HDB resale and private condos."
        ),
        "SA": CountryPack(
            country_code="SA",
            country_name="Saudi Arabia",
            flag_emoji="🇸🇦",
            currency=CurrencyPack(code="SAR", symbol="SR", display_unit="thousands_millions", exchange_rate_to_usd=3.75),
            primary_messaging_channel="whatsapp",
            compliance_framework="Real Estate General Authority (REGA Saudi Arabia)",
            tax_name="RETT (Real Estate Transaction Tax)",
            default_tax_rate_pct=5.0,
            property_types=["villa", "apartment", "duplex", "land", "commercial_building"],
            major_portals=["Aqar", "Bayut KSA"],
            payment_gateway="tap",
            phone_code="+966",
            phone_regex=r"^(\+966)?(5\d{8})$",
            date_format="DD/MM/YYYY",
            ai_system_persona="Professional Saudi real estate advisor compliant with REGA licenses and Vision 2030 developments."
        )
    }

    @classmethod
    def get_country_pack(cls, country_code: str) -> CountryPack:
        code = country_code.upper().strip()
        if code not in cls._REGISTRY:
            # Fallback to International Default (US)
            return cls._REGISTRY["US"]
        return cls._REGISTRY[code]

    @classmethod
    def list_all_country_packs(cls) -> List[CountryPack]:
        return list(cls._REGISTRY.values())

    @classmethod
    def register_custom_country_pack(cls, pack: CountryPack) -> None:
        cls._REGISTRY[pack.country_code.upper()] = pack
