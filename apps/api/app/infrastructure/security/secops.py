"""
WefyLabs Security Operations (SecOps) & Security Event Taxonomy
===============================================================
Centralizes monitoring, audit logging, and operational metrics for security events:
- AUTH_FAILURE: Failed login attempts, invalid credentials, expired JWTs.
- AUTHZ_FAILURE: Role permission denials, super-admin bypass attempts.
- RATE_LIMIT: Rate limiting violations across all tiers.
- INVALID_WEBHOOK: Missing or forged HMAC signatures, malformed payloads.
- SUSPICIOUS_INPUT: SQLi patterns, path traversal attempts, script tags in CRM inputs.
- TENANT_BOUNDARY_VIOLATION: IDOR attempts, cross-tenant resource requests.
- AI_POLICY_REJECTION: Prompt injection, role spoofing, unsafe tool requests.
- SYSTEM_SECURITY_ERROR: Cryptographic failures, unhandled auth middleware exceptions.
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List

from app.common.logger.redaction import redact_string, redact_payload

logger = logging.getLogger("wefylabs.secops")


class SecurityEventType(str, Enum):
    AUTH_FAILURE = "AUTH_FAILURE"
    AUTHZ_FAILURE = "AUTHZ_FAILURE"
    RATE_LIMIT = "RATE_LIMIT"
    INVALID_WEBHOOK = "INVALID_WEBHOOK"
    SUSPICIOUS_INPUT = "SUSPICIOUS_INPUT"
    TENANT_BOUNDARY_VIOLATION = "TENANT_BOUNDARY_VIOLATION"
    AI_POLICY_REJECTION = "AI_POLICY_REJECTION"
    SYSTEM_SECURITY_ERROR = "SYSTEM_SECURITY_ERROR"


# Ring buffer of recent security events for operator diagnostics (max 200 events)
_RECENT_SECURITY_EVENTS: deque[Dict[str, Any]] = deque(maxlen=200)

# In-memory aggregate event counts
_SECURITY_EVENT_COUNTS: Dict[str, int] = {e.value: 0 for e in SecurityEventType}


def record_security_event(
    event_type: SecurityEventType,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    ip: Optional[str] = None,
    details: Optional[str] = None,
    severity: str = "MEDIUM"
) -> Dict[str, Any]:
    """
    Records a structured security event with sanitization and redaction.
    Never logs secrets or customer PII.
    """
    event_type_str = event_type.value if isinstance(event_type, SecurityEventType) else str(event_type)
    
    # Increment counter
    if event_type_str in _SECURITY_EVENT_COUNTS:
        _SECURITY_EVENT_COUNTS[event_type_str] += 1
    else:
        _SECURITY_EVENT_COUNTS[event_type_str] = 1

    sanitized_details = redact_string(details or "")
    event_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type_str,
        "tenant_id": str(tenant_id) if tenant_id else "unauthenticated",
        "user_id": str(user_id) if user_id else "anonymous",
        "ip": str(ip) if ip else "unknown",
        "details": sanitized_details[:500],
        "severity": severity,
    }

    _RECENT_SECURITY_EVENTS.append(event_record)

    log_level = logging.WARNING if severity in ("LOW", "MEDIUM") else logging.ERROR
    logger.log(
        log_level,
        f"[SecOps Event] type={event_type_str} tenant={event_record['tenant_id']} "
        f"ip={event_record['ip']} severity={severity} details={sanitized_details}"
    )

    return event_record


def get_recent_security_events(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns recent security events (operator diagnostic view)."""
    return list(_RECENT_SECURITY_EVENTS)[-limit:]


def get_security_event_metrics() -> Dict[str, int]:
    """Returns aggregate security event counts."""
    return dict(_SECURITY_EVENT_COUNTS)
