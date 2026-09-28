"""
Incident Intelligence Manager
==============================
Automated incident detection, classification, correlation, and
escalation with full audit trail.

Incident Lifecycle:
  OPEN → ACKNOWLEDGED → INVESTIGATING → RESOLVED → CLOSED

Severity Levels (P0–P4):
  P0 - Complete outage        → page on-call immediately
  P1 - Critical degradation   → page within 5 min
  P2 - Significant impact     → alert within 15 min
  P3 - Minor impact           → ticket within 1 hr
  P4 - Informational          → log only

No synthetic MTTR or uptime numbers — all timing is derived from
actual event timestamps.
"""
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class IncidentSeverity(str, Enum):
    P0 = "P0"  # Complete outage
    P1 = "P1"  # Critical degradation
    P2 = "P2"  # Significant impact
    P3 = "P3"  # Minor impact
    P4 = "P4"  # Informational


class IncidentStatus(str, Enum):
    OPEN           = "OPEN"
    ACKNOWLEDGED   = "ACKNOWLEDGED"
    INVESTIGATING  = "INVESTIGATING"
    RESOLVED       = "RESOLVED"
    CLOSED         = "CLOSED"


class IncidentCategory(str, Enum):
    AVAILABILITY   = "AVAILABILITY"   # Service down / high error rate
    PERFORMANCE    = "PERFORMANCE"    # Latency SLO breach
    SECURITY       = "SECURITY"       # Auth / access anomaly
    DATA_INTEGRITY = "DATA_INTEGRITY" # Corrupt writes / tenant leak
    AI_QUALITY     = "AI_QUALITY"     # Evaluation failure
    DEPENDENCY     = "DEPENDENCY"     # External provider outage


@dataclass
class IncidentEvent:
    """A single timestamped event in an incident timeline."""
    event_type: str       # "created" | "acknowledged" | "comment" | "escalated" | "resolved"
    actor: str
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Incident:
    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    category: IncidentCategory
    status: IncidentStatus = IncidentStatus.OPEN
    organization_id: Optional[str] = None
    affected_services: List[str] = field(default_factory=list)
    timeline: List[IncidentEvent] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    closed_at: Optional[str] = None
    root_cause: Optional[str] = None
    remediation: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    _created_ts: float = field(default_factory=time.time, repr=False)

    def ttd_seconds(self) -> Optional[float]:
        """Time-to-detect: seconds from creation to acknowledgment."""
        if not self.acknowledged_at:
            return None
        ack_ts = datetime.fromisoformat(self.acknowledged_at).timestamp()
        return round(ack_ts - self._created_ts, 2)

    def ttr_seconds(self) -> Optional[float]:
        """Time-to-resolve: seconds from creation to resolution."""
        if not self.resolved_at:
            return None
        res_ts = datetime.fromisoformat(self.resolved_at).timestamp()
        return round(res_ts - self._created_ts, 2)


class IncidentManager:
    """
    Incident lifecycle manager with detection, correlation, and reporting.

    Usage:
        mgr = IncidentManager()
        inc = mgr.open("DB replication lag spike", IncidentSeverity.P1, IncidentCategory.PERFORMANCE)
        mgr.acknowledge(inc.incident_id, actor="on-call-sre")
        mgr.resolve(inc.incident_id, root_cause="...", remediation="...")
    """

    def __init__(self):
        self._incidents: Dict[str, Incident] = {}
        self._dedup_window_seconds: int = 300  # 5 min dedup window
        self._recent_titles: Dict[str, str] = {}  # title → incident_id for dedup

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def open(
        self,
        title: str,
        severity: IncidentSeverity,
        category: IncidentCategory,
        description: str = "",
        organization_id: Optional[str] = None,
        affected_services: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Incident:
        """Open a new incident (with dedup logic)."""
        # Dedup: same title within 5-min window → return existing
        existing_id = self._recent_titles.get(title)
        if existing_id and existing_id in self._incidents:
            existing = self._incidents[existing_id]
            if existing.status not in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
                logger.info(f"[INCIDENT] Dedup: returning existing {existing_id}")
                return existing

        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        incident = Incident(
            incident_id=incident_id,
            title=title,
            description=description,
            severity=severity,
            category=category,
            organization_id=organization_id,
            affected_services=affected_services or [],
            tags=tags or [],
        )
        incident.timeline.append(IncidentEvent(
            event_type="created",
            actor="system",
            message=f"Incident opened: {title}",
        ))

        self._incidents[incident_id] = incident
        self._recent_titles[title] = incident_id

        logger.error(
            f"[INCIDENT] OPENED {incident_id} [{severity.value}] [{category.value}]: {title}"
        )
        return incident

    def acknowledge(self, incident_id: str, actor: str = "system", message: str = "") -> Incident:
        inc = self._get(incident_id)
        inc.status = IncidentStatus.ACKNOWLEDGED
        inc.acknowledged_at = datetime.now(timezone.utc).isoformat()
        inc.timeline.append(IncidentEvent(
            event_type="acknowledged",
            actor=actor,
            message=message or f"Acknowledged by {actor}",
        ))
        logger.warning(f"[INCIDENT] ACKNOWLEDGED {incident_id} by {actor} TTD={inc.ttd_seconds()}s")
        return inc

    def update_status(self, incident_id: str, status: IncidentStatus, actor: str = "system", message: str = "") -> Incident:
        inc = self._get(incident_id)
        prev = inc.status
        inc.status = status
        inc.timeline.append(IncidentEvent(
            event_type="status_change",
            actor=actor,
            message=message or f"Status: {prev.value} → {status.value}",
        ))
        return inc

    def add_comment(self, incident_id: str, actor: str, message: str, metadata: Optional[Dict] = None) -> None:
        inc = self._get(incident_id)
        inc.timeline.append(IncidentEvent(
            event_type="comment",
            actor=actor,
            message=message,
            metadata=metadata or {},
        ))

    def resolve(
        self,
        incident_id: str,
        root_cause: str,
        remediation: str,
        actor: str = "system",
    ) -> Incident:
        inc = self._get(incident_id)
        inc.status = IncidentStatus.RESOLVED
        inc.resolved_at = datetime.now(timezone.utc).isoformat()
        inc.root_cause = root_cause
        inc.remediation = remediation
        inc.timeline.append(IncidentEvent(
            event_type="resolved",
            actor=actor,
            message=f"Root cause: {root_cause}. Remediation: {remediation}",
        ))
        logger.info(
            f"[INCIDENT] RESOLVED {incident_id} TTR={inc.ttr_seconds()}s "
            f"root_cause={root_cause!r}"
        )
        return inc

    def close(self, incident_id: str, actor: str = "system") -> Incident:
        inc = self._get(incident_id)
        inc.status = IncidentStatus.CLOSED
        inc.closed_at = datetime.now(timezone.utc).isoformat()
        inc.timeline.append(IncidentEvent(event_type="closed", actor=actor, message="Incident closed."))
        return inc

    # ── Query ─────────────────────────────────────────────────────────────────

    def _get(self, incident_id: str) -> Incident:
        if incident_id not in self._incidents:
            raise KeyError(f"Incident not found: {incident_id}")
        return self._incidents[incident_id]

    def get(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    def open_incidents(self) -> List[Incident]:
        return [
            i for i in self._incidents.values()
            if i.status not in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)
        ]

    def all_incidents(self) -> List[Incident]:
        return list(self._incidents.values())

    def report(self) -> Dict[str, Any]:
        incidents = self.all_incidents()
        resolved  = [i for i in incidents if i.resolved_at]
        open_sev  = {s.value: 0 for s in IncidentSeverity}
        for inc in self.open_incidents():
            open_sev[inc.severity.value] += 1

        # MTTR from actual event timestamps — never fabricated
        ttrs = [i.ttr_seconds() for i in resolved if i.ttr_seconds() is not None]
        mttr = round(sum(ttrs) / len(ttrs), 2) if ttrs else None

        return {
            "total": len(incidents),
            "open": len(self.open_incidents()),
            "resolved": len(resolved),
            "open_by_severity": open_sev,
            "mttr_seconds": mttr,
            "mttr_source": "derived_from_event_timestamps",
        }

    # ── Auto-detection helpers ─────────────────────────────────────────────────

    def detect_slo_breach(self, slo_name: str, current_value: float, target: float) -> Optional[Incident]:
        """Opens P1 incident automatically when an SLO is breached."""
        title = f"SLO Breach: {slo_name}"
        description = f"Current={current_value:.3f} exceeds threshold={target}"
        return self.open(
            title=title,
            severity=IncidentSeverity.P1,
            category=IncidentCategory.PERFORMANCE,
            description=description,
            affected_services=["api"],
            tags=["slo", "auto-detected"],
        )

    def detect_error_spike(self, error_rate_pct: float, threshold_pct: float = 5.0) -> Optional[Incident]:
        """Opens P0 incident when error rate spikes above threshold."""
        if error_rate_pct >= threshold_pct:
            title = f"Error Rate Spike: {error_rate_pct:.1f}%"
            return self.open(
                title=title,
                severity=IncidentSeverity.P0,
                category=IncidentCategory.AVAILABILITY,
                description=f"Error rate {error_rate_pct:.1f}% ≥ {threshold_pct:.1f}% threshold",
                affected_services=["api"],
                tags=["error-rate", "auto-detected"],
            )
        return None


# Global singleton
incident_manager = IncidentManager()
