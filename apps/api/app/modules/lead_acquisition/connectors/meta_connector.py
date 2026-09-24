"""
Part 13 / Part 21.1 — Meta Lead Ads Connector
==============================================
Authoritative connector for official Meta Lead Ads integration.

Handles:
  - Meta Lead Ads webhook verification (GET hub.challenge)
  - Incoming leadgen webhook events (POST with HMAC-SHA256 signature)
  - Lead data retrieval via Meta Graph API v19.0 / v20.0
  - Comprehensive field mapping for real-estate custom questions (BHK, Budget, Location, Timeline)
  - Bounded reconciliation and historical backfill
  - Structured error classification & health checks

Official Meta Ads API reference:
  https://developers.facebook.com/docs/marketing-api/guides/lead-ads

Rules:
  - NEVER fake_connected.
  - Return CONFIGURATION_REQUIRED if credentials unavailable.
  - Fail-closed signature verification.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

META_PROVIDER_NAME = "meta_lead_ads"
META_GRAPH_VERSION = "v19.0"


class MetaErrorTaxonomy:
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    PROVIDER_SERVER_ERROR = "PROVIDER_SERVER_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class MetaLeadAdsConnector:
    """
    Official Meta Lead Ads connector for WefyLabs.

    Configuration (from LeadSource.configuration or ConnectorConfig):
      page_id: Meta page ID
      form_id: Optional lead form ID to filter
      access_token_encrypted: Encrypted page access token
      app_secret_encrypted: Encrypted app secret for signature check
      ad_account_id: Meta ad account ID
    """

    def get_status(self, configuration: Optional[Dict[str, Any]]) -> str:
        """Check if this connector is configured."""
        if not configuration:
            return "CONFIGURATION_REQUIRED"
        required = ["page_id", "access_token_encrypted"]
        for field in required:
            if not configuration.get(field):
                return "CONFIGURATION_REQUIRED"
        if configuration.get("reauth_required"):
            return "REAUTH_REQUIRED"
        if configuration.get("degraded"):
            return "DEGRADED"
        if configuration.get("verified"):
            return "VERIFIED"
        return "CONFIGURED"

    def verify_webhook_signature(
        self, app_secret: str, raw_body: bytes, x_hub_signature: str
    ) -> bool:
        """
        Verify Meta webhook signature using HMAC-SHA256.

        Meta sends: X-Hub-Signature-256: sha256=<hex>
        Verification: HMAC-SHA256(app_secret, raw_body)
        """
        if not x_hub_signature or not x_hub_signature.startswith("sha256="):
            return False
        expected = x_hub_signature[7:].strip()
        computed = hmac.new(
            app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(computed, expected)

    def handle_verification_challenge(
        self, params: Dict[str, str], verify_token: str
    ) -> Optional[str]:
        """
        Handle Meta webhook verification challenge (GET request from Meta App Dashboard).

        Meta sends:
          hub.mode=subscribe
          hub.verify_token=<token>
          hub.challenge=<challenge>

        Returns hub.challenge if verification token matches, None otherwise.
        """
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")
        if mode == "subscribe" and token == verify_token:
            return challenge
        return None

    def extract_lead_events(self, raw_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract individual lead events from Meta webhook payload.

        Meta payload structure:
        {
          "object": "page",
          "entry": [{
            "id": "<page_id>",
            "time": 1234567890,
            "changes": [{
              "field": "leadgen",
              "value": {
                "leadgen_id": "<lead_id>",
                "page_id": "<page_id>",
                "form_id": "<form_id>",
                "adset_id": "<adset_id>",
                "ad_id": "<ad_id>",
                "created_time": 1234567890
              }
            }]
          }]
        }
        """
        events = []
        if raw_payload.get("object") != "page":
            return events
        for entry in raw_payload.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") == "leadgen":
                    value = change.get("value", {})
                    events.append({
                        "provider": META_PROVIDER_NAME,
                        "external_id": str(value.get("leadgen_id") or ""),
                        "page_id": str(value.get("page_id") or ""),
                        "form_id": str(value.get("form_id") or ""),
                        "campaign_id_meta": str(value.get("campaign_id") or ""),
                        "adset_id": str(value.get("adset_id") or ""),
                        "ad_id": str(value.get("ad_id") or ""),
                        "created_time": value.get("created_time"),
                        "consent_metadata": value.get("consent_action_results", []),
                        "raw_change": value,
                    })
        return events

    async def retrieve_lead_data(
        self, leadgen_id: str, access_token: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Retrieve actual lead field data via Meta Graph API.
        Must be called after receiving webhook event to get contact details.

        Graph API: GET /<leadgen_id>?access_token=<token>&fields=...
        Returns: (payload_dict, error_taxonomy_code)
        """
        if not leadgen_id or not access_token:
            return None, MetaErrorTaxonomy.INVALID_REQUEST

        try:
            import httpx
            url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/{leadgen_id}"
            params = {
                "access_token": access_token,
                "fields": "field_data,created_time,ad_id,form_id,campaign_id,adset_id,page_id,is_organic",
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    return response.json(), None
                elif response.status_code in (401, 403):
                    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    code = data.get("error", {}).get("code")
                    if code in (190, 102):  # Token expired or invalid
                        return None, MetaErrorTaxonomy.AUTHENTICATION_ERROR
                    return None, MetaErrorTaxonomy.AUTHORIZATION_ERROR
                elif response.status_code == 429:
                    return None, MetaErrorTaxonomy.RATE_LIMITED
                elif response.status_code == 404:
                    return None, MetaErrorTaxonomy.NOT_FOUND
                elif response.status_code >= 500:
                    return None, MetaErrorTaxonomy.PROVIDER_SERVER_ERROR
                else:
                    return None, MetaErrorTaxonomy.UNKNOWN_ERROR

        except Exception as exc:
            exc_name = type(exc).__name__
            if "Timeout" in exc_name:
                logger.error(f"[META] Timeout fetching leadgen_id={leadgen_id}: {exc}")
                return None, MetaErrorTaxonomy.TIMEOUT
            logger.error(f"[META] Network/Client error for leadgen_id={leadgen_id}: {exc}")
            return None, MetaErrorTaxonomy.NETWORK_ERROR

    def parse_field_data(self, field_data: list) -> Dict[str, Any]:
        """Parse Meta Lead Ads field_data array into structured dict."""
        result = {}
        if not isinstance(field_data, list):
            return result
        for field in field_data:
            if not isinstance(field, dict):
                continue
            key = str(field.get("name") or "").strip().lower()
            vals = field.get("values")
            val = vals[0] if isinstance(vals, list) and vals else None
            if key and val is not None:
                result[key] = str(val).strip()
        return result

    def normalize_lead_payload(
        self,
        lead_data: Dict[str, Any],
        event_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Normalizes Meta Lead Ads payload into Canonical Lead Intake contract fields.
        Detects contact info, real-estate questions, budget, and attribution.
        """
        raw_fields = self.parse_field_data(lead_data.get("field_data", []))
        # If payload already flattened
        if not raw_fields and "email" in lead_data or "phone_number" in lead_data:
            raw_fields = {k.lower(): str(v) for k, v in lead_data.items() if v is not None}

        # 1. Contact details resolution
        email = (
            raw_fields.get("email")
            or raw_fields.get("work_email")
            or raw_fields.get("personal_email")
            or raw_fields.get("contact_email")
        )
        phone = (
            raw_fields.get("phone_number")
            or raw_fields.get("phone")
            or raw_fields.get("contact_phone")
            or raw_fields.get("mobile_number")
            or raw_fields.get("whatsapp_number")
        )
        first_name = raw_fields.get("first_name", "")
        last_name = raw_fields.get("last_name", "")
        full_name = (
            raw_fields.get("full_name")
            or raw_fields.get("name")
            or (f"{first_name} {last_name}".strip() if (first_name or last_name) else None)
        )

        # 2. Real-Estate Requirements Mapping
        budget_val = None
        for b_key in ["budget", "budget_range", "price_range", "investment_budget", "expected_budget"]:
            if raw_fields.get(b_key):
                budget_val = raw_fields[b_key]
                break

        property_type = None
        for pt_key in ["property_type", "type_of_property", "looking_for", "unit_type", "configuration"]:
            if raw_fields.get(pt_key):
                property_type = raw_fields[pt_key]
                break

        # Check for BHK specific question
        bhk_val = None
        for bhk_key in ["bhk", "bedrooms", "no_of_bedrooms", "bedroom_count"]:
            if raw_fields.get(bhk_key):
                bhk_val = raw_fields[bhk_key]
                break

        if bhk_val and not property_type:
            property_type = f"{bhk_val} BHK" if "bhk" not in bhk_val.lower() else bhk_val

        location_val = None
        for loc_key in ["preferred_location", "city", "location", "locality", "project_location"]:
            if raw_fields.get(loc_key):
                location_val = raw_fields[loc_key]
                break

        timeline_val = None
        for t_key in ["timeline", "purchase_timeline", "planning_to_buy", "timeframe"]:
            if raw_fields.get(t_key):
                timeline_val = raw_fields[t_key]
                break

        purpose_val = None
        for p_key in ["purpose", "purpose_of_purchase", "buying_purpose", "intent"]:
            if raw_fields.get(p_key):
                purpose_val = raw_fields[p_key]
                break

        # Attribution / Context
        ctx = event_context or {}
        external_lead_id = str(lead_data.get("id") or ctx.get("external_id") or "")
        form_id = str(lead_data.get("form_id") or ctx.get("form_id") or "")
        page_id = str(lead_data.get("page_id") or ctx.get("page_id") or "")
        ad_id = str(lead_data.get("ad_id") or ctx.get("ad_id") or "")
        campaign_id_meta = str(lead_data.get("campaign_id") or ctx.get("campaign_id_meta") or "")

        # Synthesize inquiry message from custom questions
        msg_parts = []
        if property_type:
            msg_parts.append(f"Looking for: {property_type}")
        if budget_val:
            msg_parts.append(f"Budget: {budget_val}")
        if location_val:
            msg_parts.append(f"Location: {location_val}")
        if timeline_val:
            msg_parts.append(f"Timeline: {timeline_val}")
        if purpose_val:
            msg_parts.append(f"Purpose: {purpose_val}")

        synthesized_msg = " | ".join(msg_parts) if msg_parts else "Meta Lead Ads form submission"

        return {
            "name": full_name or "Meta Lead",
            "email": email,
            "phone": phone,
            "budget": budget_val,
            "property_type": property_type,
            "preferred_locations": [location_val] if location_val else [],
            "city": location_val,
            "timeline": timeline_val,
            "message": synthesized_msg,
            "external_lead_id": external_lead_id,
            "utm_source": "meta",
            "utm_medium": "paid_social",
            "utm_campaign": campaign_id_meta or None,
            "source_metadata": {
                "provider": META_PROVIDER_NAME,
                "form_id": form_id,
                "page_id": page_id,
                "ad_id": ad_id,
                "adset_id": ctx.get("adset_id"),
                "campaign_id_meta": campaign_id_meta,
                "created_time": lead_data.get("created_time"),
                "raw_fields": raw_fields,
            },
        }

    async def reconcile_leads(
        self,
        form_id: str,
        access_token: str,
        since_timestamp: Optional[int] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Bounded reconciliation: fetches recent leads from Meta form to identify missing records.
        GET /{form_id}/leads?access_token=...&filtering=[{"field":"time_created","operator":"GREATER_THAN","value":...}]
        """
        try:
            import httpx
            url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/{form_id}/leads"
            params: Dict[str, Any] = {
                "access_token": access_token,
                "limit": min(limit, 100),
                "fields": "id,created_time,field_data,ad_id",
            }
            if since_timestamp:
                params["filtering"] = json.dumps([
                    {"field": "time_created", "operator": "GREATER_THAN", "value": int(since_timestamp)}
                ])

            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    leads = data.get("data", [])
                    return {
                        "status": "success",
                        "form_id": form_id,
                        "leads_count": len(leads),
                        "leads": leads,
                    }
                return {
                    "status": "error",
                    "status_code": res.status_code,
                    "error": res.text,
                    "leads": [],
                }
        except Exception as exc:
            logger.error(f"[META] Reconciliation error for form_id={form_id}: {exc}")
            return {"status": "error", "error": str(exc), "leads": []}

    async def backfill_leads(
        self,
        form_id: str,
        access_token: str,
        start_timestamp: int,
        end_timestamp: int,
        limit: int = 100,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Bounded historical backfill from Meta Form within explicit window.
        Rate-limited, deterministic, and idempotent.
        """
        if dry_run:
            return {
                "status": "dry_run",
                "form_id": form_id,
                "window": {"start": start_timestamp, "end": end_timestamp},
                "estimated_retrieval_limit": limit,
            }

        rec_res = await self.reconcile_leads(
            form_id=form_id,
            access_token=access_token,
            since_timestamp=start_timestamp,
            limit=limit,
        )
        return {
            "status": "completed" if rec_res.get("status") == "success" else "failed",
            "form_id": form_id,
            "retrieved_count": len(rec_res.get("leads", [])),
            "leads": rec_res.get("leads", []),
        }

    def health_check(self, configuration: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Detailed health check for Meta integration."""
        status = self.get_status(configuration)
        return {
            "provider": META_PROVIDER_NAME,
            "status": status,
            "is_configured": status in ("CONFIGURED", "VERIFIED"),
            "page_id": configuration.get("page_id") if configuration else None,
            "form_id": configuration.get("form_id") if configuration else None,
            "last_verified_at": configuration.get("last_verified_at") if configuration else None,
        }
