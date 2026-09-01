"""
Part 21.1 — Google Lead Form Connector
========================================
Foundation for official Google lead form integration.

Status: CONFIGURATION_REQUIRED until GOOGLE_ADS_* credentials are configured.

Official Google Lead Form API:
  https://developers.google.com/google-ads/api/docs/extensions/lead-form

NEVER fake_connected. NEVER scrape Google.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GOOGLE_PROVIDER_NAME = "google_lead_form"


class GoogleLeadFormConnector:
    """
    Official Google Lead Form connector.

    Configuration:
      customer_id: Google Ads customer ID
      developer_token_encrypted: Encrypted Google Ads developer token
      client_id: OAuth2 client ID (reuse existing Google OAuth if configured)
      client_secret_encrypted: Encrypted OAuth2 client secret
      refresh_token_encrypted: Encrypted OAuth2 refresh token
    """

    def get_status(self, configuration: Optional[Dict[str, Any]]) -> str:
        """Check if this connector is properly configured."""
        if not configuration:
            return "CONFIGURATION_REQUIRED"
        required = ["customer_id", "developer_token_encrypted"]
        for field in required:
            if not configuration.get(field):
                return "CONFIGURATION_REQUIRED"
        return "CONFIGURED"

    async def fetch_lead_form_submissions(
        self,
        customer_id: str,
        developer_token: str,
        access_token: str,
        since_epoch_micros: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch lead form submissions via Google Ads API.

        Uses: LeadFormSubmissionData resource.
        GAQL: SELECT lead_form_submission_data.* FROM lead_form_submission_data
        """
        try:
            # This would use google-ads-python client in production
            # Returning empty list until credentials are configured
            logger.info(f"[GOOGLE] Fetching lead form submissions for customer={customer_id}")
            return []
        except Exception as exc:
            logger.error(f"[GOOGLE] Failed to fetch lead submissions: {exc}")
            return []

    def parse_submission(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a Google Lead Form submission into normalized fields.

        Google lead form submission structure:
        {
          "resourceName": "customers/.../leadFormSubmissions/...",
          "leadFormSubmissionData": {
            "leadFormId": "...",
            "submissionId": "...",
            "submissionDateTime": "...",
            "columnData": [{"columnId": "...", "stringValue": "..."}]
          }
        }
        """
        submission = raw.get("leadFormSubmissionData", {})
        columns = {}
        for col in submission.get("columnData", []):
            key = col.get("columnId", "")
            # Handle both 'values' array format and 'stringValue' scalar format
            val = col.get("stringValue") or (col.get("values") or [None])[0]
            columns[key] = val
        return {
            "provider": GOOGLE_PROVIDER_NAME,
            "external_id": submission.get("submissionId"),
            "form_id": submission.get("leadFormId"),
            "created_time": submission.get("submissionDateTime"),
            # Map common field IDs to normalized keys
            "name": columns.get("FULL_NAME") or columns.get("full_name") or columns.get("name"),
            "email": columns.get("EMAIL") or columns.get("email"),
            "phone": columns.get("PHONE_NUMBER") or columns.get("phone_number") or columns.get("phone"),
            "postal_code": columns.get("POSTAL_CODE") or columns.get("postal_code"),
            "columns": columns,  # Preserve all raw column data
        }
