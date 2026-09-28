"""
Part 13 / Part 21.1 — 99acres Real Estate Portal Connector
==========================================================
Authoritative connector for 99acres real-estate portal enquiry integration.

Handles:
  - 99acres webhook key / auth token verification
  - Portal enquiry payload parsing (enquiry_id, property_id, BHK, budget, locality)
  - Real-estate requirement normalization
  - Idempotency & tenant-safe routing
"""
from __future__ import annotations

import hmac
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

NINETY_NINE_ACRES_PROVIDER_NAME = "99acres"


class NinetyNineAcresErrorTaxonomy:
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    INVALID_KEY = "INVALID_KEY"
    INVALID_REQUEST = "INVALID_REQUEST"
    PAYLOAD_MALFORMED = "PAYLOAD_MALFORMED"


class NinetyNineAcresConnector:
    """
    Official 99acres portal connector for WefyLabs.

    Configuration:
      portal_key: 99acres webhook / API key
      portal_key_encrypted: Encrypted key
    """

    def get_status(self, configuration: Optional[Dict[str, Any]]) -> str:
        if not configuration:
            return "CONFIGURATION_REQUIRED"
        has_key = bool(
            configuration.get("portal_key")
            or configuration.get("portal_key_encrypted")
            or configuration.get("api_key")
            or configuration.get("key")
            or configuration.get("token")
        )
        if not has_key:
            return "CONFIGURATION_REQUIRED"
        if configuration.get("degraded"):
            return "DEGRADED"
        if configuration.get("verified"):
            return "VERIFIED"
        return "CONFIGURED"

    def verify_webhook_key(self, expected_key: str, provided_key: Optional[str]) -> bool:
        if not expected_key or not provided_key:
            return False
        return hmac.compare_digest(expected_key.strip(), provided_key.strip())

    def parse_submission(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize 99acres enquiry payload into canonical intake fields.
        """
        lookup: Dict[str, Any] = {str(k).lower(): v for k, v in raw.items()}

        external_id = str(
            lookup.get("enquiry_id")
            or lookup.get("lead_id")
            or lookup.get("leadid")
            or lookup.get("query_id")
            or lookup.get("id")
            or ""
        ).strip()

        name = (
            lookup.get("name")
            or lookup.get("cust_name")
            or lookup.get("sender_name")
            or lookup.get("contact_name")
            or lookup.get("buyer_name")
        )

        phone = (
            lookup.get("phone")
            or lookup.get("mobile")
            or lookup.get("contact_num")
            or lookup.get("cust_phone")
            or lookup.get("phone_number")
        )

        email = (
            lookup.get("email")
            or lookup.get("cust_email")
            or lookup.get("sender_email")
        )

        prop_id = str(
            lookup.get("property_id")
            or lookup.get("prop_id")
            or lookup.get("project_id")
            or lookup.get("listing_id")
            or ""
        ).strip() or None

        prop_type = (
            lookup.get("property_type")
            or lookup.get("prop_type")
            or lookup.get("unit_type")
            or lookup.get("configuration")
        )

        bhk = lookup.get("bhk") or lookup.get("bedroom_count") or lookup.get("bedrooms")
        if bhk and not prop_type:
            prop_type = f"{bhk} BHK" if "bhk" not in str(bhk).lower() else str(bhk)

        budget = (
            lookup.get("budget")
            or lookup.get("price")
            or lookup.get("expected_budget")
            or lookup.get("budget_max")
        )

        city = lookup.get("city") or lookup.get("city_name")
        locality = lookup.get("locality") or lookup.get("location") or lookup.get("project_name")
        preferred_locations = []
        if locality:
            preferred_locations.append(str(locality).strip())
        if city and str(city).strip() not in preferred_locations:
            preferred_locations.append(str(city).strip())

        query_text = (
            lookup.get("query")
            or lookup.get("message")
            or lookup.get("remarks")
            or lookup.get("requirement")
            or ""
        )

        msg_parts = []
        if prop_id:
            msg_parts.append(f"Property Ref: {prop_id}")
        if prop_type:
            msg_parts.append(f"Looking for: {prop_type}")
        if locality:
            msg_parts.append(f"Locality: {locality}")
        if query_text:
            msg_parts.append(f"Enquiry: {query_text}")
        synthesized_msg = " | ".join(msg_parts) if msg_parts else "99acres Portal Enquiry"

        return {
            "external_id": external_id,
            "name": str(name).strip() if name else "99acres Lead",
            "phone": str(phone).strip() if phone else None,
            "email": str(email).strip() if email else None,
            "property_id": prop_id,
            "property_type": str(prop_type).strip() if prop_type else None,
            "budget": str(budget).strip() if budget else None,
            "city": str(city).strip() if city else (str(locality).strip() if locality else None),
            "preferred_locations": preferred_locations,
            "message": synthesized_msg,
            "utm_source": "99acres",
            "utm_medium": "portal",
            "utm_campaign": prop_id or None,
            "source_metadata": {
                "provider": NINETY_NINE_ACRES_PROVIDER_NAME,
                "property_id": prop_id,
                "locality": locality,
                "city": city,
                "raw_enquiry_id": external_id,
            },
        }
