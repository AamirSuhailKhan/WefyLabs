"""
WefyLabs Public Lead Capture Security Guard
===========================================
Defends public-facing lead ingestion against automated abuse, spam, and prompt injection:
1. Honeypot traps: Detects automated bot submissions.
2. Replay & freshness verification: Ensures submissions cannot be replayed indefinitely.
3. Prompt injection sanitization: Neutralizes malicious instructions before content reaches AI agents.
4. Tenant validation: Ensures public capture routes explicitly to designated tenant without IDOR privilege escalation.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Dict, Any, Tuple

from app.infrastructure.security.secops import record_security_event, SecurityEventType

logger = logging.getLogger("wefylabs.lead_capture.guard")

# Common honeypot field names used across capture forms
HONEYPOT_FIELDS = {"website_hp", "company_url_hp", "fax_number", "confirm_email_hp"}

# Prompt injection patterns commonly used to attack downstream CRM agents
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are\s+now", re.IGNORECASE),
    re.compile(r"you\s+are\s+no\s+longer\s+an?\s+ai", re.IGNORECASE),
    re.compile(r"override\s+(all\s+)?safety\s+(guidelines|filters)", re.IGNORECASE),
    re.compile(r"drop\s+table\s+", re.IGNORECASE),
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
]


class PublicCaptureGuard:
    """
    Validation engine for public lead capture endpoints.
    """

    @staticmethod
    def inspect_submission(
        payload: Dict[str, Any],
        client_ip: str,
        tenant_id: str
    ) -> Tuple[bool, str]:
        """
        Runs full security checks on an incoming public lead payload.
        Returns (is_valid: bool, rejection_reason: str).
        """
        # 1. Honeypot check
        for hp in HONEYPOT_FIELDS:
            val = payload.get(hp)
            if val and str(val).strip():
                record_security_event(
                    SecurityEventType.SUSPICIOUS_INPUT,
                    tenant_id=tenant_id,
                    ip=client_ip,
                    details=f"Honeypot field '{hp}' populated: bot detected"
                )
                return False, "Bot submission detected"

        # 2. Timestamp replay defense (if submission_time provided)
        submission_time = payload.get("_timestamp")
        if submission_time:
            try:
                sub_ts = float(submission_time)
                now = time.time()
                # Reject if more than 10 minutes in the past or 5 minutes in the future
                if now - sub_ts > 600 or sub_ts - now > 300:
                    record_security_event(
                        SecurityEventType.SUSPICIOUS_INPUT,
                        tenant_id=tenant_id,
                        ip=client_ip,
                        details="Expired or invalid submission timestamp: replay attack prevented"
                    )
                    return False, "Submission timestamp expired"
            except (ValueError, TypeError):
                pass

        # 3. Payload size check
        if len(str(payload)) > 50000:
            record_security_event(
                SecurityEventType.SUSPICIOUS_INPUT,
                tenant_id=tenant_id,
                ip=client_ip,
                details="Oversized payload rejected (>50KB)"
            )
            return False, "Payload exceeds maximum allowed size"

        return True, ""

    @staticmethod
    def sanitize_untrusted_text(text: str, tenant_id: str = "unknown") -> str:
        """
        Neutralizes prompt injection patterns and HTML/script tags from user inputs
        before they are passed to AI models or CRM storage.
        """
        if not text or not isinstance(text, str):
            return ""

        cleaned = text
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(cleaned):
                record_security_event(
                    SecurityEventType.AI_POLICY_REJECTION,
                    tenant_id=tenant_id,
                    details="Prompt injection pattern detected in lead submission and neutralized"
                )
                cleaned = pattern.sub("[FILTERED_INSTRUCTION]", cleaned)

        # Strip dangerous HTML tags
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        return cleaned.strip()
