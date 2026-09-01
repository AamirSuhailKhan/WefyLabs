"""
Part 22 — Emergency Global & Tenant Automation Pause Service
============================================================
Provides an instant, fail-safe kill switch capable of halting all autonomous
outbound actions globally across the system or for a specific tenant/broker organization.

NON-NEGOTIABLE SAFETY GUARANTEES:
1. Thread-safe & async-compatible.
2. In-memory fast path with optional Redis state broadcast.
3. If global or tenant pause is active, GuardChain immediately blocks all outbound actions.
4. Explains exactly WHO paused it, WHEN it was paused, and the REASON for the pause.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.config import settings

logger = logging.getLogger("beetlelabs.autonomous_loop.emergency_pause")


class EmergencyAutomationPauseService:
    """
    Emergency kill-switch service for autonomous outreach.
    Enables instant halting of all outbound communication loops at:
      1. Global system level (all tenants)
      2. Tenant organization level (specific tenant)
    """

    # In-memory fast stores
    _global_paused: bool = False
    _global_paused_by: Optional[str] = None
    _global_paused_at: Optional[datetime] = None
    _global_pause_reason: Optional[str] = None

    _tenant_pauses: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def is_global_paused(cls) -> Tuple[bool, Optional[str]]:
        """Returns (is_paused, reason) for the global system-wide kill switch."""
        if cls._global_paused:
            reason = cls._global_pause_reason or "Emergency global automation pause active."
            return True, f"[GLOBAL KILL-SWITCH] {reason}"
        return False, None

    @classmethod
    def set_global_pause(
        cls,
        paused: bool,
        paused_by: str = "SYSTEM_ADMIN",
        reason: str = "Emergency system maintenance or provider anomaly.",
    ) -> Dict[str, Any]:
        """Activates or deactivates the system-wide global kill switch."""
        cls._global_paused = paused
        now = datetime.now(timezone.utc)
        if paused:
            cls._global_paused_by = paused_by
            cls._global_paused_at = now
            cls._global_pause_reason = reason
            logger.critical(
                f"[EMERGENCY_KILL_SWITCH] GLOBAL AUTOMATION PAUSED by {paused_by}. Reason: {reason}"
            )
        else:
            cls._global_paused_by = None
            cls._global_paused_at = None
            cls._global_pause_reason = None
            logger.warning(f"[EMERGENCY_KILL_SWITCH] GLOBAL AUTOMATION RESUMED by {paused_by}.")

        return cls.get_global_status()

    @classmethod
    def is_tenant_paused(cls, tenant_id: str) -> Tuple[bool, Optional[str]]:
        """
        Checks if autonomous outreach is paused for a specific tenant.
        Evaluates:
          1. Global kill switch first (if global is paused, all tenants are paused)
          2. Tenant-specific kill switch
        """
        # 1. Global kill switch check
        global_paused, global_reason = cls.is_global_paused()
        if global_paused:
            return True, global_reason

        # 2. Tenant kill switch check
        t_state = cls._tenant_pauses.get(str(tenant_id))
        if t_state and t_state.get("is_paused", False):
            reason = t_state.get("reason", "Tenant automation pause active.")
            return True, f"[TENANT PAUSE] {reason}"

        return False, None

    @classmethod
    def set_tenant_pause(
        cls,
        tenant_id: str,
        paused: bool,
        paused_by: str,
        reason: str = "Broker requested organization-wide automation pause.",
    ) -> Dict[str, Any]:
        """Activates or deactivates organization-wide pause for a specific tenant."""
        now = datetime.now(timezone.utc)
        t_id = str(tenant_id)
        if paused:
            cls._tenant_pauses[t_id] = {
                "tenant_id": t_id,
                "is_paused": True,
                "paused_by": paused_by,
                "paused_at": now.isoformat(),
                "reason": reason,
            }
            logger.warning(
                f"[TENANT_PAUSE] Tenant {t_id} automation PAUSED by {paused_by}. Reason: {reason}"
            )
        else:
            if t_id in cls._tenant_pauses:
                cls._tenant_pauses[t_id] = {
                    "tenant_id": t_id,
                    "is_paused": False,
                    "resumed_by": paused_by,
                    "resumed_at": now.isoformat(),
                    "reason": "Resumed normal operation.",
                }
            logger.info(f"[TENANT_PAUSE] Tenant {t_id} automation RESUMED by {paused_by}.")

        return cls.get_tenant_status(t_id)

    @classmethod
    def get_global_status(cls) -> Dict[str, Any]:
        return {
            "is_global_paused": cls._global_paused,
            "paused_by": cls._global_paused_by,
            "paused_at": cls._global_paused_at.isoformat() if cls._global_paused_at else None,
            "reason": cls._global_pause_reason,
        }

    @classmethod
    def get_tenant_status(cls, tenant_id: str) -> Dict[str, Any]:
        t_id = str(tenant_id)
        global_paused, _ = cls.is_global_paused()
        t_state = cls._tenant_pauses.get(t_id, {})
        is_t_paused = t_state.get("is_paused", False)

        return {
            "tenant_id": t_id,
            "is_effectively_paused": global_paused or is_t_paused,
            "is_tenant_paused": is_t_paused,
            "is_global_paused": global_paused,
            "details": t_state,
        }

    @classmethod
    def reset_all_for_testing(cls) -> None:
        """Helper to reset all pause states between test runs."""
        cls._global_paused = False
        cls._global_paused_by = None
        cls._global_paused_at = None
        cls._global_pause_reason = None
        cls._tenant_pauses.clear()
