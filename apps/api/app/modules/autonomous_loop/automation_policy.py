"""
Part 21.8 — Autonomous Sales Loop Automation Policy Engine
===========================================================
Deterministic, AI-proof permission lookup for autonomous actions.

INVARIANT:
  AI systems NEVER determine their own authorization.
  This policy engine is purely deterministic Python code.
  It maps SalesActionType → AutomationPermission based on policy configuration.

Policy categories:
  AUTOMATIC       — Execute without broker approval if guards permit
  HUMAN_APPROVAL  — Block execution until broker explicitly approves
  FORBIDDEN       — Never automate, always fail safe
  SCHEDULED       — Defer to policy-determined timing window
  NO_ACTION       — Nothing to do right now
"""
import logging
from typing import Optional

from app.models.follow_up_models import FollowUpPolicy
from app.modules.sales_action.taxonomies import SalesActionType
from app.modules.autonomous_loop.taxonomies import AutomationPermission

logger = logging.getLogger(__name__)

POLICY_VERSION = "v1.0-autonomy"


class AutonomyPolicyEngine:
    """
    Declarative autonomy policy lookup engine.
    All permissions are hard-coded by action type.
    Only the autonomy_level from FollowUpPolicy can restrict automation further.
    """

    # Base permission table (AI cannot override this)
    _BASE_PERMISSIONS: dict[SalesActionType, AutomationPermission] = {
        # ── Fully Automatic Actions ─────────────────────────────────────────
        SalesActionType.ASK_QUALIFICATION:          AutomationPermission.AUTOMATIC,
        SalesActionType.SEND_PROPERTY_RECOMMENDATIONS: AutomationPermission.AUTOMATIC,
        SalesActionType.SEND_PROPERTY_DETAILS:      AutomationPermission.AUTOMATIC,
        SalesActionType.OFFER_VIEWING:              AutomationPermission.AUTOMATIC,
        SalesActionType.CONFIRM_VIEWING:            AutomationPermission.AUTOMATIC,
        SalesActionType.VIEWING_REMINDER:           AutomationPermission.AUTOMATIC,
        SalesActionType.POST_VIEWING_FOLLOW_UP:     AutomationPermission.AUTOMATIC,
        SalesActionType.FOLLOW_UP_NO_RESPONSE:      AutomationPermission.AUTOMATIC,
        SalesActionType.FOLLOW_UP_PROPERTY_SENT:    AutomationPermission.AUTOMATIC,
        SalesActionType.FOLLOW_UP_AFTER_INQUIRY:    AutomationPermission.AUTOMATIC,
        SalesActionType.FOLLOW_UP_AFTER_VIEWING:    AutomationPermission.AUTOMATIC,
        SalesActionType.REQUEST_MISSING_INFORMATION: AutomationPermission.AUTOMATIC,
        # ── Require Human Approval ──────────────────────────────────────────
        SalesActionType.BOOK_VIEWING:               AutomationPermission.HUMAN_APPROVAL,
        SalesActionType.REQUEST_FINANCING_DETAILS:  AutomationPermission.HUMAN_APPROVAL,
        SalesActionType.HUMAN_HANDOFF:              AutomationPermission.HUMAN_APPROVAL,
        # ── Forbidden — Never Automate ──────────────────────────────────────
        # (No action type currently maps to FORBIDDEN in the base taxonomy,
        # but policy can escalate HUMAN_APPROVAL to FORBIDDEN at any time.)
        # ── No Action / Internal State Changes ─────────────────────────────
        SalesActionType.NO_ACTION:                  AutomationPermission.NO_ACTION,
        SalesActionType.PAUSE_OUTREACH:             AutomationPermission.NO_ACTION,
        SalesActionType.RESUME_OUTREACH:            AutomationPermission.NO_ACTION,
        SalesActionType.MARK_DORMANT:               AutomationPermission.NO_ACTION,
    }

    # Autonomy levels — higher = more autonomous
    _AUTONOMY_LEVELS = {
        "LEVEL_0": 0,  # Fully manual — nothing automated
        "LEVEL_1": 1,  # Only qualification questions
        "LEVEL_2": 2,  # Qualification + property recommendations
        "LEVEL_3": 3,  # Standard automation (default)
        "LEVEL_4": 4,  # High automation
        "LEVEL_5": 5,  # Full automation
    }

    # Minimum autonomy level required per permission
    _LEVEL_THRESHOLDS: dict[AutomationPermission, int] = {
        AutomationPermission.AUTOMATIC: 3,
        AutomationPermission.HUMAN_APPROVAL: 1,
        AutomationPermission.FORBIDDEN: 0,
        AutomationPermission.SCHEDULED: 2,
        AutomationPermission.NO_ACTION: 0,
    }

    @classmethod
    def evaluate(
        cls,
        action_type: SalesActionType,
        policy: Optional[FollowUpPolicy] = None,
        is_high_value: bool = False,
    ) -> AutomationPermission:
        """
        Evaluates automation permission for a sales action type.

        Priority:
          1. FORBIDDEN overrides — high-value threshold forces HUMAN_APPROVAL if policy requires it.
          2. Base permission lookup.
          3. Autonomy level restriction — if org's level is too low, escalate to HUMAN_APPROVAL.

        Returns AutomationPermission (never raises — unknown actions → HUMAN_APPROVAL).
        """
        # 1. Unknown action type → HUMAN_APPROVAL (fail safe)
        base_permission = cls._BASE_PERMISSIONS.get(action_type, AutomationPermission.HUMAN_APPROVAL)

        # 2. High-value transaction override
        if is_high_value and policy and policy.require_approval_high_value:
            if base_permission == AutomationPermission.AUTOMATIC:
                logger.info(
                    f"[AUTONOMY_POLICY] Action {action_type.value} escalated to "
                    f"HUMAN_APPROVAL: high-value transaction threshold triggered."
                )
                return AutomationPermission.HUMAN_APPROVAL

        # 3. Autonomy level restriction
        if policy:
            org_level_str = policy.autonomy_level or "LEVEL_3"
            org_level_int = cls._AUTONOMY_LEVELS.get(org_level_str, 3)
            required_level = cls._LEVEL_THRESHOLDS.get(base_permission, 3)

            if org_level_int < required_level:
                logger.info(
                    f"[AUTONOMY_POLICY] Action {action_type.value} restricted from "
                    f"{base_permission.value} to HUMAN_APPROVAL: org_level={org_level_str} "
                    f"requires level >={required_level}"
                )
                return AutomationPermission.HUMAN_APPROVAL

        return base_permission

    @classmethod
    def get_policy_version(cls) -> str:
        return POLICY_VERSION
