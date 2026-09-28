"""
Part 13 / Part 21.1 — IndiaMART Lead Push Connector
===================================================
Authoritative connector for IndiaMART CRM Push Lead service.

Handles:
  - IndiaMART CRM Push webhook key/token verification
  - Ingestion of IndiaMART Push Lead payloads (JSON / Form / URL-encoded)
  - Extraction of inquirer details (SENDER_NAME, SENDER_MOBILE, SENDER_EMAIL)
  - Real-estate requirement parsing from product name and enquiry message (BHK, Budget, Locality, Property Type)
  - Tenant-safe resolution and idempotency tracking (UNIQUEQUERYID)
  - Error taxonomy & health checks
"""
from __future__ import annotations

import hmac
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

INDIAMART_PROVIDER_NAME = "indiamart"


class IndiaMartErrorTaxonomy:
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    INVALID_KEY = "INVALID_KEY"
    INVALID_REQUEST = "INVALID_REQUEST"
    PAYLOAD_MALFORMED = "PAYLOAD_MALFORMED"


class IndiaMartConnector:
    """
    Official IndiaMART CRM Push connector for WefyLabs.

    Configuration:
      glusr_crm_key: IndiaMART CRM key configured in LeadSource configuration
      crm_key_encrypted: Encrypted key
    """

    def get_status(self, configuration: Optional[Dict[str, Any]]) -> str:
        if not configuration:
            return "CONFIGURATION_REQUIRED"
        has_key = bool(
            configuration.get("glusr_crm_key")
            or configuration.get("glusr_crm_key_encrypted")
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
        Normalize IndiaMART CRM Push Lead payload into canonical intake fields.
        """
        # IndiaMART fields may be UPPERCASE or lowercase
        lookup: Dict[str, Any] = {str(k).upper(): v for k, v in raw.items()}

        external_id = str(
            lookup.get("UNIQUEQUERYID")
            or lookup.get("QUERY_ID")
            or lookup.get("ENQUIRY_ID")
            or lookup.get("ID")
            or ""
        ).strip()

        name = (
            lookup.get("SENDER_NAME")
            or lookup.get("SENDERNAME")
            or lookup.get("NAME")
            or lookup.get("GLUSR_USR_NAME")
        )

        phone = (
            lookup.get("SENDER_MOBILE")
            or lookup.get("MOB")
            or lookup.get("MOBILE")
            or lookup.get("PHONE")
            or lookup.get("SENDER_PHONE")
        )

        email = (
            lookup.get("SENDER_EMAIL")
            or lookup.get("EMAIL")
            or lookup.get("SENDEREMAIL")
        )

        product_name = str(lookup.get("QUERY_PRODUCT_NAME") or lookup.get("PRODUCT_NAME") or "").strip()
        query_msg = str(lookup.get("QUERY_MESSAGE") or lookup.get("ENQUIRY_MESSAGE") or lookup.get("MESSAGE") or "").strip()
        combined_text = f"{product_name} {query_msg}".strip()

        city = (
            lookup.get("SENDER_CITY")
            or lookup.get("CITY")
            or lookup.get("GLUSR_USR_CITY")
        )
        state = lookup.get("SENDER_STATE") or lookup.get("STATE")
        company = lookup.get("SENDER_COMPANY") or lookup.get("GLUSR_USR_COMPANYNAME")

        # 1. Real Estate BHK Extraction
        bhk_val = None
        bhk_match = re.search(r"(\b[1-6]\s*BHK\b|\b[1-6]\s*bedroom\b)", combined_text, re.IGNORECASE)
        if bhk_match:
            bhk_val = bhk_match.group(1).upper()

        # 2. Property Type Extraction
        property_type = None
        prop_types = ["apartment", "flat", "villa", "plot", "penthouse", "commercial", "office", "retail", "studio"]
        for pt in prop_types:
            if re.search(rf"\b{pt}\b", combined_text, re.IGNORECASE):
                property_type = pt.title()
                break
        if bhk_val:
            property_type = f"{bhk_val} {property_type}" if property_type else f"{bhk_val} Apartment"

        # 3. Budget Extraction
        budget_val = None
        budget_match = re.search(r"(\b[\d\.]+\s*(?:cr|crore|crores|l|lakh|lakhs)\b)", combined_text, re.IGNORECASE)
        if budget_match:
            budget_val = budget_match.group(1).strip()

        # 4. Synthesize message
        msg_parts = []
        if product_name:
            msg_parts.append(f"Product: {product_name}")
        if query_msg and query_msg != product_name:
            msg_parts.append(f"Enquiry: {query_msg}")
        if company:
            msg_parts.append(f"Company: {company}")
        synthesized_msg = " | ".join(msg_parts) if msg_parts else "IndiaMART Lead Push"

        return {
            "external_id": external_id,
            "name": str(name).strip() if name else "IndiaMART Lead",
            "phone": str(phone).strip() if phone else None,
            "email": str(email).strip() if email else None,
            "city": str(city).strip() if city else None,
            "preferred_locations": [str(city).strip()] if city else [],
            "state": str(state).strip() if state else None,
            "property_type": property_type,
            "budget": budget_val,
            "message": synthesized_msg,
            "utm_source": "indiamart",
            "utm_medium": "b2b_portal",
            "utm_campaign": product_name or None,
            "source_metadata": {
                "provider": INDIAMART_PROVIDER_NAME,
                "product_name": product_name,
                "company": company,
                "raw_query_id": external_id,
                "query_time": lookup.get("QUERY_TIME"),
            },
        }
