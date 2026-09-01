"""
Part 21.8 — Deterministic Lead State Machine
=============================================
Validates lead lifecycle transitions for the autonomous sales loop.

INVARIANTS:
  - LLMs NEVER directly mutate lifecycle state.
  - Invalid transitions fail immediately and safely.
  - Every transition records: actor, reason, previous_state, new_state, timestamp.
  - Terminal states (CONVERTED, LOST, OPTED_OUT) cannot transition to active states.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Set, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.autonomous_loop.models import LeadAutomationState
from app.modules.autonomous_loop.taxonomies import LeadLifecycleState

logger = logging.getLogger(__name__)

# ── Allowed Transition Table ──────────────────────────────────────────────────
# Maps: source_state → set of valid target_states
ALLOWED_TRANSITIONS: Dict[LeadLifecycleState, Set[LeadLifecycleState]] = {
    LeadLifecycleState.NEW: {
        LeadLifecycleState.CONTACTING,
        LeadLifecycleState.HUMAN_HANDOFF,
        LeadLifecycleState.OPTED_OUT,
        LeadLifecycleState.LOST,
    },
    LeadLifecycleState.CONTACTING: {
        LeadLifecycleState.ENGAGING,
        LeadLifecycleState.DORMANT,
        LeadLifecycleState.HUMAN_HANDOFF,
        LeadLifecycleState.OPTED_OUT,
        LeadLifecycleState.LOST,
    },
    LeadLifecycleState.ENGAGING: {
        LeadLifecycleState.QUALIFYING,
        LeadLifecycleState.CONTACTING,  # re-engage after silence
        LeadLifecycleState.DORMANT,
        LeadLifecycleState.HUMAN_HANDOFF,
        LeadLifecycleState.OPTED_OUT,
        LeadLifecycleState.LOST,
    },
    LeadLifecycleState.QUALIFYING: {
        LeadLifecycleState.QUALIFIED,
        LeadLifecycleState.ENGAGING,
        LeadLifecycleState.DORMANT,
        LeadLifecycleState.HUMAN_HANDOFF,
        LeadLifecycleState.OPTED_OUT,
        LeadLifecycleState.LOST,
    },
    LeadLifecycleState.QUALIFIED: {
        LeadLifecycleState.PROPERTY_MATCHED,
        LeadLifecycleState.QUALIFYING,  # needs more information
        LeadLifecycleState.DORMANT,
        LeadLifecycleState.HUMAN_HANDOFF,
        LeadLifecycleState.OPTED_OUT,
        LeadLifecycleState.LOST,
    },
    LeadLifecycleState.PROPERTY_MATCHED: {
        LeadLifecycleState.VIEWING_PENDING,
        LeadLifecycleState.QUALIFIED,
        LeadLifecycleState.DORMANT,
        LeadLifecycleState.HUMAN_HANDOFF,
        LeadLifecycleState.OPTED_OUT,
        LeadLifecycleState.LOST,
    },
    LeadLifecycleState.VIEWING_PENDING: {
        LeadLifecycleState.VIEWING_SCHEDULED,
        LeadLifecycleState.PROPERTY_MATCHED,
        LeadLifecycleState.DORMANT,
        LeadLifecycleState.HUMAN_HANDOFF,
        LeadLifecycleState.OPTED_OUT,
        LeadLifecycleState.LOST,
    },
    LeadLifecycleState.VIEWING_SCHEDULED: {
        LeadLifecycleState.VIEWING_COMPLETED,
        LeadLifecycleState.VIEWING_PENDING,  # rescheduled
        LeadLifecycleState.PROPERTY_MATCHED,  # cancelled
        LeadLifecycleState.DORMANT,
        LeadLifecycleState.HUMAN_HANDOFF,
        LeadLifecycleState.OPTED_OUT,
        LeadLifecycleState.LOST,
    },
    LeadLifecycleState.VIEWING_COMPLETED: {
        LeadLifecycleState.NEGOTIATION,
        LeadLifecycleState.PROPERTY_MATCHED,  # wants different property
        LeadLifecycleState.DORMANT,
        LeadLifecycleState.HUMAN_HANDOFF,
        LeadLifecycleState.OPTED_OUT,
        LeadLifecycleState.LOST,
    },
    LeadLifecycleState.NEGOTIATION: {
        LeadLifecycleState.BOOKING,
        LeadLifecycleState.VIEWING_COMPLETED,
        LeadLifecycleState.HUMAN_HANDOFF,
        LeadLifecycleState.DORMANT,
        LeadLifecycleState.OPTED_OUT,
        LeadLifecycleState.LOST,
    },
    LeadLifecycleState.BOOKING: {
        LeadLifecycleState.CONVERTED,
        LeadLifecycleState.NEGOTIATION,
        LeadLifecycleState.HUMAN_HANDOFF,
        LeadLifecycleState.LOST,
    },
    # Terminal states — only self-transition allowed (idempotent)
    LeadLifecycleState.CONVERTED: {
        LeadLifecycleState.CONVERTED,
    },
    LeadLifecycleState.LOST: {
        LeadLifecycleState.LOST,
    },
    LeadLifecycleState.OPTED_OUT: {
        LeadLifecycleState.OPTED_OUT,
    },
    # Exceptional states — can resume
    LeadLifecycleState.DORMANT: {
        LeadLifecycleState.CONTACTING,
        LeadLifecycleState.ENGAGING,
        LeadLifecycleState.LOST,
        LeadLifecycleState.OPTED_OUT,
    },
    LeadLifecycleState.HUMAN_HANDOFF: {
        LeadLifecycleState.CONTACTING,
        LeadLifecycleState.ENGAGING,
        LeadLifecycleState.QUALIFYING,
        LeadLifecycleState.NEGOTIATION,
        LeadLifecycleState.CONVERTED,
        LeadLifecycleState.LOST,
        LeadLifecycleState.OPTED_OUT,
    },
}

# Terminal states where automation must NEVER proceed
TERMINAL_STATES: Set[LeadLifecycleState] = {
    LeadLifecycleState.CONVERTED,
    LeadLifecycleState.LOST,
    LeadLifecycleState.OPTED_OUT,
}

# States where autonomous outbound communication is forbidden
NO_OUTBOUND_STATES: Set[LeadLifecycleState] = {
    LeadLifecycleState.OPTED_OUT,
    LeadLifecycleState.HUMAN_HANDOFF,
    LeadLifecycleState.CONVERTED,   # Terminal: no post-conversion autonomous outreach
}


class LeadStateMachine:
    """
    Deterministic lead lifecycle state machine.
    Validates and records all transitions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_automation_state(
        self, lead_id: str, tenant_id: str
    ) -> LeadAutomationState:
        """Loads or initializes automation state for a lead.

        SECURITY: Enforces tenant isolation. If a lead already has automation state
        under another tenant, raises PermissionError to prevent cross-tenant access.
        """
        stmt = select(LeadAutomationState).where(
            LeadAutomationState.lead_id == lead_id
        )
        res = await self.db.execute(stmt)
        state = res.scalars().first()

        if state:
            if str(state.tenant_id) != str(tenant_id):
                logger.error(
                    f"[STATE_MACHINE] TENANT VIOLATION: lead={lead_id} belongs to tenant={state.tenant_id}, "
                    f"attempted access by tenant={tenant_id}"
                )
                raise PermissionError(
                    f"Access denied: Lead {lead_id} does not belong to tenant {tenant_id}."
                )
            return state

        state = LeadAutomationState(
            lead_id=lead_id,
            tenant_id=tenant_id,
            current_lifecycle_state=LeadLifecycleState.NEW.value,
            is_paused=False,
            is_broker_takeover=False,
            daily_action_count=0,
            orchestration_depth=0,
            consecutive_failures=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(state)
        await self.db.flush()
        logger.info(
            f"[STATE_MACHINE] Created automation state: lead={lead_id} tenant={tenant_id}"
        )

        return state

    def validate_transition(
        self,
        from_state: LeadLifecycleState,
        to_state: LeadLifecycleState,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates a lifecycle transition.
        Returns (is_valid, error_message).
        """
        if from_state == to_state:
            return True, None
        allowed = ALLOWED_TRANSITIONS.get(from_state, set())
        if to_state in allowed:
            return True, None
        return (
            False,
            f"Invalid lifecycle transition: {from_state.value} → {to_state.value}. "
            f"Allowed targets from {from_state.value}: {[s.value for s in allowed]}",
        )

    async def request_transition(
        self,
        lead_id: str,
        tenant_id: str,
        to_state: LeadLifecycleState,
        actor: str,
        reason: str,
    ) -> Tuple[bool, Optional[str], Optional[LeadAutomationState]]:
        """
        Requests a lifecycle transition. Validates and persists if allowed.
        Returns (success, error_message, updated_state).
        """
        state = await self.get_or_create_automation_state(lead_id, tenant_id)

        try:
            from_state = LeadLifecycleState(state.current_lifecycle_state)
        except ValueError:
            from_state = LeadLifecycleState.NEW

        # Idempotent: same state → no-op success
        if from_state == to_state:
            return True, None, state

        is_valid, error = self.validate_transition(from_state, to_state)
        if not is_valid:
            logger.warning(
                f"[STATE_MACHINE] Invalid transition rejected: lead={lead_id} "
                f"{from_state.value}→{to_state.value} actor={actor}"
            )
            return False, error, state

        # Apply transition
        state.previous_lifecycle_state = state.current_lifecycle_state
        state.current_lifecycle_state = to_state.value
        state.state_changed_at = datetime.now(timezone.utc)
        state.state_change_reason = f"[{actor}] {reason}"
        state.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            f"[STATE_MACHINE] Transition applied: lead={lead_id} "
            f"{from_state.value}→{to_state.value} actor={actor}"
        )
        return True, None, state

    def is_terminal(self, state: LeadLifecycleState) -> bool:
        """Returns True if this is a terminal state (no further autonomous action)."""
        return state in TERMINAL_STATES

    def allows_outbound(self, state: LeadLifecycleState) -> bool:
        """Returns True if outbound autonomous communication is permitted in this state."""
        return state not in NO_OUTBOUND_STATES
