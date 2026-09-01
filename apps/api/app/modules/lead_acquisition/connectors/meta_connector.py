"""
Part 21.1 — Meta Lead Ads Connector
=====================================
Foundation for official Meta Lead Ads integration.

Status: CONFIGURATION_REQUIRED until META_ACCESS_TOKEN is set.

This connector handles:
  - Meta Lead Ads webhook verification (hub.challenge)
  - Incoming leadgen webhook events
  - Lead data retrieval via Meta Graph API

Official Meta Ads API reference:
  https://developers.facebook.com/docs/marketing-api/guides/lead-ads

NEVER fake_connected. NEVER scrape Meta.
If credentials unavailable: return CONFIGURATION_REQUIRED.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

META_PROVIDER_NAME = "meta_lead_ads"


class MetaLeadAdsConnector:
    """
    Official Meta Lead Ads connector.

    Configuration (from LeadSource.configuration):
      page_id: Meta page ID
      form_id: Lead form ID (optional — filters events to specific form)
      access_token_encrypted: Encrypted page access token (from ConnectorConfig / SecretsManager)
      app_secret_encrypted: Encrypted app secret for webhook signature verification
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
        return "CONFIGURED"

    def verify_webhook_signature(
        self, app_secret: str, raw_body: bytes, x_hub_signature: str
    ) -> bool:
        """
        Verify Meta webhook signature using HMAC-SHA256.

        Meta sends: X-Hub-Signature-256: sha256=<hex>
        Verification: HMAC-SHA256(app_secret, raw_body)
        """
        if not x_hub_signature.startswith("sha256="):
            return False
        expected = x_hub_signature[7:]  # Remove "sha256=" prefix
        computed = hmac.new(
            app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(computed, expected)

    def handle_verification_challenge(self, params: Dict[str, str], verify_token: str) -> Optional[str]:
        """
        Handle Meta webhook verification challenge.

        Returns hub.challenge if verification token matches, None otherwise.
        """
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")
        if mode == "subscribe" and token == verify_token:
            return challenge
        return None

    def extract_lead_events(self, raw_payload: Dict[str, Any]) -> list:
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
                        "external_id": value.get("leadgen_id"),
                        "page_id": value.get("page_id"),
                        "form_id": value.get("form_id"),
                        "campaign_id_meta": value.get("campaign_id"),
                        "adset_id": value.get("adset_id"),
                        "ad_id": value.get("ad_id"),
                        "created_time": value.get("created_time"),
                        # field_data populated by separate Graph API call — not available in webhook
                        "field_data": [],
                        "consent_metadata": value.get("consent_action_results", []),
                    })
        return events

    async def retrieve_lead_data(
        self, leadgen_id: str, access_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve actual lead field data via Meta Graph API.
        Must be called after receiving webhook event to get contact details.

        Graph API: GET /<leadgen_id>?access_token=<token>
        """
        try:
            import httpx
            url = f"https://graph.facebook.com/v19.0/{leadgen_id}"
            params = {"access_token": access_token, "fields": "field_data,created_time,ad_id,form_id,campaign_id"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
                logger.warning(f"[META] Graph API returned {response.status_code} for leadgen_id={leadgen_id}")
                return None
        except Exception as exc:
            logger.error(f"[META] Failed to retrieve lead data: {exc}")
            return None

    def parse_field_data(self, field_data: list) -> Dict[str, Any]:
        """Parse Meta Lead Ads field_data array into structured dict."""
        result = {}
        for field in field_data:
            key = field.get("name", "")
            value = field.get("values", [None])[0]
            result[key] = value
        return result
