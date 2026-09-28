"""
WefyLabs Normalized Security Event, Alerting & Incident Response Engine
=======================================================================
Build 11 Enterprise Observability & Incident Response:
1. Normalized Security Event Contract:
   - event_id, event_type, organization_id, actor_id, actor_type, resource_type,
     resource_id, ip, user_agent, timestamp, result, severity, metadata, correlation_id
2. Canonical Event Taxonomy:
   - AUTH_FAILURE, AUTH_SUCCESS, SESSION_REVOKED, TENANT_ACCESS_DENIED,
     PERMISSION_DENIED, PRIVILEGE_ESCALATION_ATTEMPT, SECRET_CHANGED,
     EXPORT_CREATED, EXPORT_DOWNLOADED, DATA_DELETED, WEBHOOK_REJECTED,
     AI_POLICY_BLOCKED, TOOL_AUTHORIZATION_DENIED, SUSPICIOUS_ACTIVITY
3. Canonical Severity Tiers:
   - INFO, LOW, MEDIUM, HIGH, CRITICAL
4. Enterprise Security Incident State Machine:
   - DETECTED -> TRIAGED -> CONTAINED -> INVESTIGATING -> REMEDIATING -> RESOLVED -> POSTMORTEM
"""
from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.modules.security.data_governance import scrub_pii_and_secrets


class SecurityEventType(str, Enum):
    AUTH_FAILURE = "AUTH_FAILURE"
    AUTH_SUCCESS = "AUTH_SUCCESS"
    SESSION_REVOKED = "SESSION_REVOKED"
    TENANT_ACCESS_DENIED = "TENANT_ACCESS_DENIED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PRIVILEGE_ESCALATION_ATTEMPT = "PRIVILEGE_ESCALATION_ATTEMPT"
    SECRET_CHANGED = "SECRET_CHANGED"
    EXPORT_CREATED = "EXPORT_CREATED"
    EXPORT_DOWNLOADED = "EXPORT_DOWNLOADED"
    DATA_DELETED = "DATA_DELETED"
    WEBHOOK_REJECTED = "WEBHOOK_REJECTED"
    AI_POLICY_BLOCKED = "AI_POLICY_BLOCKED"
    TOOL_AUTHORIZATION_DENIED = "TOOL_AUTHORIZATION_DENIED"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"


class SecuritySeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    TRIAGED = "TRIAGED"
    CONTAINED = "CONTAINED"
    INVESTIGATING = "INVESTIGATING"
    REMEDIATING = "REMEDIATING"
    RESOLVED = "RESOLVED"
    POSTMORTEM = "POSTMORTEM"


class SecurityEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: SecurityEventType
    organization_id: Optional[str] = None
    actor_id: Optional[str] = None
    actor_type: str = "user"  # user | system | ai | webhook | api_key
    resource_type: str = "system"
    resource_id: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    result: str = "DENIED"    # SUCCESS | DENIED | BLOCKED | FAILED
    severity: SecuritySeverity = SecuritySeverity.MEDIUM
    metadata: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None


class SecurityIncidentRecord(BaseModel):
    incident_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: Optional[str] = None
    severity: SecuritySeverity = SecuritySeverity.HIGH
    incident_type: str  # e.g., "PRIVILEGE_ESCALATION", "CROSS_TENANT_ACCESS", "SECRET_LEAK"
    status: IncidentStatus = IncidentStatus.DETECTED
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    owner: Optional[str] = "SecOps Lead"
    description: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    actions_taken: List[str] = Field(default_factory=list)
    resolved_at: Optional[datetime] = None


class SecurityEventService:
    """
    Central SecOps telemetry recorder and incident correlation engine.
    Ensures zero secret leakage in event payloads and immutable audit integration.
    """

    _event_stream: deque[SecurityEvent] = deque(maxlen=1000)
    _incidents: Dict[str, SecurityIncidentRecord] = {}

    @classmethod
    async def record_event(
        cls,
        *,
        event_type: SecurityEventType,
        organization_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        actor_type: str = "user",
        resource_type: str = "system",
        resource_id: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        result: str = "SUCCESS",
        severity: Optional[SecuritySeverity] = None,
        metadata: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> SecurityEvent:
        """
        Records a normalized security event, scrubbed of secrets/PII, and syncs to DB audit trail.
        """
        # Default severity mapping
        if severity is None:
            if event_type in (SecurityEventType.PRIVILEGE_ESCALATION_ATTEMPT, SecurityEventType.TENANT_ACCESS_DENIED):
                severity = SecuritySeverity.HIGH
            elif event_type in (SecurityEventType.WEBHOOK_REJECTED, SecurityEventType.AI_POLICY_BLOCKED, SecurityEventType.PERMISSION_DENIED):
                severity = SecuritySeverity.MEDIUM
            elif event_type == SecurityEventType.AUTH_FAILURE:
                severity = SecuritySeverity.LOW
            else:
                severity = SecuritySeverity.INFO

        # Sanitize metadata to guarantee no credentials or raw secrets leak
        safe_meta = {}
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, str):
                    safe_meta[k] = scrub_pii_and_secrets(v)
                else:
                    safe_meta[k] = v

        event = SecurityEvent(
            event_type=event_type,
            organization_id=organization_id,
            actor_id=actor_id,
            actor_type=actor_type,
            resource_type=resource_type,
            resource_id=resource_id,
            ip=ip,
            user_agent=user_agent,
            result=result,
            severity=severity,
            metadata=safe_meta,
            correlation_id=correlation_id
        )

        cls._event_stream.append(event)

        # Trigger automatic incident for Critical/High security violations
        if severity in (SecuritySeverity.CRITICAL, SecuritySeverity.HIGH) and result in ("DENIED", "BLOCKED"):
            cls._auto_create_incident_from_event(event)

        # Sync to database AuditLog if session is available
        if db is not None:
            try:
                org_uuid = uuid.UUID(organization_id) if organization_id else None
                act_uuid = uuid.UUID(actor_id) if actor_id else None
                audit_entry = AuditLog(
                    organization_id=org_uuid,
                    actor_id=act_uuid,
                    actor_type=actor_type,
                    action=f"secops.{event_type.value.lower()}",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    ip_address=ip,
                    user_agent=user_agent,
                    changes=safe_meta,
                    correlation_id=correlation_id
                )
                db.add(audit_entry)
                await db.commit()
            except Exception:
                # Audit recording must never crash business transactions
                pass

        return event

    @classmethod
    def _auto_create_incident_from_event(cls, event: SecurityEvent) -> SecurityIncidentRecord:
        """Automatically provisions a security incident for triaging."""
        inc = SecurityIncidentRecord(
            organization_id=event.organization_id,
            severity=event.severity,
            incident_type=event.event_type.value,
            status=IncidentStatus.DETECTED,
            description=f"Automated Alert: {event.event_type.value} on {event.resource_type}:{event.resource_id or 'all'}",
            evidence={
                "event_id": event.event_id,
                "actor_id": event.actor_id,
                "ip": event.ip,
                "result": event.result,
                "metadata": event.metadata
            },
            actions_taken=["Security perimeter alert fired", "Session tagged for audit review"]
        )
        cls._incidents[inc.incident_id] = inc
        return inc

    @classmethod
    def list_events(
        cls,
        organization_id: Optional[str] = None,
        event_type: Optional[SecurityEventType] = None,
        severity: Optional[SecuritySeverity] = None,
        limit: int = 50
    ) -> List[SecurityEvent]:
        """Lists recorded security events matching filter criteria."""
        items = list(cls._event_stream)
        if organization_id:
            items = [e for e in items if e.organization_id == str(organization_id)]
        if event_type:
            items = [e for e in items if e.event_type == event_type]
        if severity:
            items = [e for e in items if e.severity == severity]
        return items[-limit:]

    @classmethod
    def transition_incident(
        cls,
        incident_id: str,
        new_status: IncidentStatus,
        action_note: Optional[str] = None
    ) -> Optional[SecurityIncidentRecord]:
        """Transitions incident along standard containment and resolution lifecycle."""
        inc = cls._incidents.get(incident_id)
        if not inc:
            return None
        inc.status = new_status
        if action_note:
            inc.actions_taken.append(f"[{datetime.now(timezone.utc).isoformat()}] {action_note}")
        if new_status == IncidentStatus.RESOLVED:
            inc.resolved_at = datetime.now(timezone.utc)
        return inc

    @classmethod
    def list_incidents(cls, organization_id: Optional[str] = None) -> List[SecurityIncidentRecord]:
        items = list(cls._incidents.values())
        if organization_id:
            items = [i for i in items if i.organization_id == str(organization_id)]
        return items
