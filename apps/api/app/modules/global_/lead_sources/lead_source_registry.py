"""
LeadSourceRegistry & Universal Source Normalizer
================================================
Spec §40–43 — Lead Source Registry & Adapters.

Normalizes incoming lead payloads from any portal or ad network worldwide
into the universal Lead model without country-specific hacks or fragmented tables.

Supported Source Categories:
  - Property Portals: Property Finder (UAE), Bayut (UAE/KSA), Dubizzle (UAE),
                      99acres (IN), Magicbricks (IN), Housing.com (IN),
                      Rightmove (GB), Zoopla (GB), Aqar (SA), Zillow/Realtor (US)
  - Social & Ads: Meta Lead Ads (FB/IG), Google Ads, TikTok Ads, LinkedIn
  - Direct: Website Form, WhatsApp Inbound, Webhook, REST API, CSV Import, Referral
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from decimal import Decimal

from app.modules.global_.phone.phone_service import PhoneService

logger = logging.getLogger(__name__)


@dataclass
class NormalizedLeadPayload:
    """Universal normalized lead payload produced by all source adapters."""
    source_provider: str                       # e.g., "property_finder", "meta_ads", "99acres"
    source_category: str                       # PORTAL | SOCIAL_ADS | DIRECT | WEBHOOK | CSV | REFERRAL
    country_code: Optional[str]                # ISO Alpha-2
    market_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None                # Normalized E.164
    raw_phone: Optional[str] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    budget_currency: Optional[str] = None
    preferred_locations: List[str] = field(default_factory=list)
    preferred_property_types: List[str] = field(default_factory=list)
    bedrooms: Optional[str] = None
    timeline: Optional[str] = None
    notes: Optional[str] = None
    external_lead_id: Optional[str] = None
    external_listing_id: Optional[str] = None
    campaign_name: Optional[str] = None
    ad_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    consent_obtained: bool = False
    consent_details: Dict[str, Any] = field(default_factory=dict)

    def to_lead_dict(self) -> Dict[str, Any]:
        """Maps directly into Lead model fields."""
        data = {
            "name": self.name or "New Lead",
            "email": self.email,
            "phone": self.phone,
            "source": self.source_provider,
            "preferred_locations": self.preferred_locations,
            "preferred_property_types": self.preferred_property_types,
            "notes": self.notes,
            "metadata_payload": {
                **self.metadata,
                "external_lead_id": self.external_lead_id,
                "external_listing_id": self.external_listing_id,
                "campaign_name": self.campaign_name,
                "ad_id": self.ad_id,
                "source_category": self.source_category,
            }
        }
        if self.budget_max is not None:
            data["budget_max"] = float(self.budget_max)
        if self.budget_min is not None:
            data["budget_min"] = float(self.budget_min)
        if self.budget_currency:
            data["budget_currency"] = self.budget_currency
        if self.country_code:
            data["country_code"] = self.country_code
        if self.market_id:
            data["market_id"] = self.market_id
        return data


class BaseLeadSourceAdapter:
    """Interface for source-specific webhook/payload normalizers."""
    provider_name: str = "generic"
    category: str = "DIRECT"
    supported_countries: List[str] = []

    def normalize(self, raw_payload: Dict[str, Any], default_country: Optional[str] = None) -> NormalizedLeadPayload:
        raise NotImplementedError


# ─── Portal Adapters ─────────────────────────────────────────────────────────

class PropertyFinderAdapter(BaseLeadSourceAdapter):
    """UAE / MENA Property Finder webhook adapter."""
    provider_name = "property_finder"
    category = "PORTAL"
    supported_countries = ["AE", "QA", "BH", "EG", "SA"]

    def normalize(self, raw_payload: Dict[str, Any], default_country: Optional[str] = "AE") -> NormalizedLeadPayload:
        country = raw_payload.get("country") or default_country or "AE"
        phone_raw = raw_payload.get("phone") or raw_payload.get("phone_number") or raw_payload.get("mobile")
        normalized_phone = PhoneService.normalize_to_e164(phone_raw, default_region=country) if phone_raw else None

        budget = None
        if raw_payload.get("budget"):
            try:
                budget = Decimal(str(raw_payload["budget"]))
            except Exception:
                pass

        return NormalizedLeadPayload(
            source_provider=self.provider_name,
            source_category=self.category,
            country_code=country,
            name=raw_payload.get("name") or raw_payload.get("full_name") or raw_payload.get("client_name"),
            email=raw_payload.get("email"),
            phone=normalized_phone,
            raw_phone=phone_raw,
            budget_max=budget,
            budget_currency=raw_payload.get("currency") or "AED",
            preferred_locations=[raw_payload["location"]] if raw_payload.get("location") else [],
            preferred_property_types=[raw_payload["property_type"]] if raw_payload.get("property_type") else [],
            bedrooms=str(raw_payload.get("bedrooms")) if raw_payload.get("bedrooms") else None,
            external_lead_id=str(raw_payload.get("id") or raw_payload.get("lead_id") or ""),
            external_listing_id=str(raw_payload.get("reference") or raw_payload.get("property_id") or ""),
            notes=raw_payload.get("message") or raw_payload.get("enquiry"),
            metadata=raw_payload,
            consent_obtained=True,
            consent_details={"source": "property_finder_portal", "scope": "inquiry"},
        )


class NinetyNineAcresAdapter(BaseLeadSourceAdapter):
    """India 99acres webhook adapter."""
    provider_name = "99acres"
    category = "PORTAL"
    supported_countries = ["IN"]

    def normalize(self, raw_payload: Dict[str, Any], default_country: Optional[str] = "IN") -> NormalizedLeadPayload:
        phone_raw = raw_payload.get("mobile") or raw_payload.get("cntct_num") or raw_payload.get("phone")
        normalized_phone = PhoneService.normalize_to_e164(phone_raw, default_region="IN") if phone_raw else None

        budget = None
        if raw_payload.get("budget"):
            try:
                budget = Decimal(str(raw_payload["budget"]))
            except Exception:
                pass

        return NormalizedLeadPayload(
            source_provider=self.provider_name,
            source_category=self.category,
            country_code="IN",
            name=raw_payload.get("name") or raw_payload.get("fname") or "99acres Lead",
            email=raw_payload.get("email"),
            phone=normalized_phone,
            raw_phone=phone_raw,
            budget_max=budget,
            budget_currency="INR",
            preferred_locations=[raw_payload["locality"]] if raw_payload.get("locality") else [],
            preferred_property_types=[raw_payload["prop_type"]] if raw_payload.get("prop_type") else [],
            bedrooms=str(raw_payload.get("bhk")) if raw_payload.get("bhk") else None,
            external_lead_id=str(raw_payload.get("query_id") or ""),
            notes=raw_payload.get("comments") or raw_payload.get("msg"),
            metadata=raw_payload,
            consent_obtained=True,
            consent_details={"source": "99acres_query", "scope": "inquiry"},
        )


class MetaLeadAdsAdapter(BaseLeadSourceAdapter):
    """Meta (Facebook / Instagram) Lead Ads Webhook Adapter."""
    provider_name = "meta_ads"
    category = "SOCIAL_ADS"
    supported_countries = ["*"]

    def normalize(self, raw_payload: Dict[str, Any], default_country: Optional[str] = None) -> NormalizedLeadPayload:
        field_data = {f["name"]: f["values"][0] for f in raw_payload.get("field_data", []) if f.get("name") and f.get("values")}
        
        name = field_data.get("full_name") or field_data.get("first_name") or raw_payload.get("name")
        email = field_data.get("email") or raw_payload.get("email")
        phone_raw = field_data.get("phone_number") or field_data.get("phone") or raw_payload.get("phone")

        inferred_country = default_country or PhoneService.extract_country_code(phone_raw or "")
        normalized_phone = PhoneService.normalize_to_e164(phone_raw, default_region=inferred_country) if phone_raw else None

        return NormalizedLeadPayload(
            source_provider=self.provider_name,
            source_category=self.category,
            country_code=inferred_country,
            name=name,
            email=email,
            phone=normalized_phone,
            raw_phone=phone_raw,
            campaign_name=raw_payload.get("campaign_name"),
            ad_id=str(raw_payload.get("ad_id") or ""),
            external_lead_id=str(raw_payload.get("leadgen_id") or ""),
            metadata={"raw_fields": field_data, **raw_payload},
            consent_obtained=True,
            consent_details={"source": "meta_lead_form", "scope": "marketing"},
        )


class UniversalLeadNormalizer:
    """
    Registry and routing engine for all incoming lead sources.
    """
    _ADAPTERS: Dict[str, BaseLeadSourceAdapter] = {
        "property_finder": PropertyFinderAdapter(),
        "99acres": NinetyNineAcresAdapter(),
        "meta_ads": MetaLeadAdsAdapter(),
        "facebook": MetaLeadAdsAdapter(),
        "instagram": MetaLeadAdsAdapter(),
    }

    @classmethod
    def register_adapter(cls, name: str, adapter: BaseLeadSourceAdapter) -> None:
        cls._ADAPTERS[name.lower()] = adapter

    @classmethod
    def normalize_payload(
        cls,
        source_name: str,
        raw_payload: Dict[str, Any],
        default_country: Optional[str] = None
    ) -> NormalizedLeadPayload:
        """
        Routes the raw payload through the appropriate registered source adapter,
        or uses generic smart fallback normalization.
        """
        adapter = cls._ADAPTERS.get(source_name.lower())
        if adapter:
            return adapter.normalize(raw_payload, default_country=default_country)

        # Generic Normalization Fallback
        phone_raw = (
            raw_payload.get("phone") or raw_payload.get("mobile") or
            raw_payload.get("phone_number") or raw_payload.get("contact") or
            raw_payload.get("telephone")
        )
        inferred_country = default_country or (PhoneService.extract_country_code(str(phone_raw)) if phone_raw else None)
        normalized_phone = PhoneService.normalize_to_e164(str(phone_raw), default_region=inferred_country) if phone_raw else None

        return NormalizedLeadPayload(
            source_provider=source_name,
            source_category="GENERIC_WEBHOOK",
            country_code=inferred_country,
            name=raw_payload.get("name") or raw_payload.get("full_name") or "Inbound Lead",
            email=raw_payload.get("email"),
            phone=normalized_phone,
            raw_phone=str(phone_raw) if phone_raw else None,
            budget_currency=raw_payload.get("currency"),
            preferred_locations=[raw_payload["location"]] if raw_payload.get("location") else [],
            notes=raw_payload.get("message") or raw_payload.get("notes"),
            metadata=raw_payload,
            consent_obtained=raw_payload.get("consent_obtained", False),
        )
