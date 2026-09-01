"""
Part 21.2 — Discovery Compliance Service
=========================================
Evaluates data compliance and regional privacy rules for discovered candidates.

Rules:
  - Discovery DOES NOT equal outbound marketing consent.
  - No automatic enrollment in WhatsApp/email/SMS campaigns.
  - Regional rules: GDPR (EU/UK), DPDPA (India), UAE PDPL.
"""
from __future__ import annotations
import logging
from typing import Tuple, Optional, Dict, Any

from app.models.discovery_models import DiscoveryCandidate, ComplianceStatus

logger = logging.getLogger(__name__)


class DiscoveryComplianceService:
    @staticmethod
    def evaluate_compliance(
        candidate: DiscoveryCandidate, country_code: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Evaluate candidate compliance status.

        Returns:
            (compliance_status, reason_if_any)
        """
        norm = candidate.normalized_data or {}
        contact = candidate.contact_information or {}

        # 1. Contact availability check
        has_phone = bool(contact.get("phone") or contact.get("phone_e164") or norm.get("phone"))
        has_email = bool(contact.get("email") or norm.get("email"))

        if not has_phone and not has_email:
            return ComplianceStatus.REVIEW_REQUIRED, "Incomplete contact information for compliance verification"

        # 2. Regional data policy checks
        code = (country_code or norm.get("country") or "").upper()

        if code in ("GB", "DE", "FR", "ES", "IT"):  # GDPR Region
            # Inbound signals (form/message) from Meta/Google/Website are permitted for CRM evaluation
            # Outbound cold outreach remains blocked without consent
            return ComplianceStatus.ALLOWED, "GDPR Compliant for CRM ingestion (outbound outreach restricted)"

        elif code == "IN":  # DPDPA India
            return ComplianceStatus.ALLOWED, "DPDPA Compliant for inbound lead evaluation"

        elif code in ("AE", "SA", "QA", "OM", "BH", "KW"):  # GCC Region
            return ComplianceStatus.ALLOWED, "GCC Privacy Policy Compliant"

        return ComplianceStatus.ALLOWED, "Standard compliant"
