"""
Calendar & Meeting Domain Events
================================
Defines domain events emitted across the appointment and viewing lifecycle.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

def create_calendar_event(
    event_type: str,
    organization_id: str,
    broker_id: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Constructs a standardized domain event payload for the BeetleLabs Event Bus.
    """
    return {
        "event_id": f"evt_{datetime.now(timezone.utc).timestamp()}",
        "event_type": event_type,
        "organization_id": organization_id,
        "broker_id": broker_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }
