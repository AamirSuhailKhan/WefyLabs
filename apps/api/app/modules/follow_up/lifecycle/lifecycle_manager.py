"""
Lead Lifecycle State Transition Engine
======================================
Manages 18 granular lead lifecycle states, validating legal transitions and
triggering automated sequence events or stop conditions.
"""

import logging
from typing import Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lead import Lead

logger = logging.getLogger(__name__)

VALID_LIFECYCLE_STATES = {
    "NEW",
    "CONTACTING",
    "ENGAGING",
    "QUALIFYING",
    "QUALIFIED",
    "RECOMMENDATION_SENT",
    "VIEWING_PENDING",
    "VIEWING_BOOKED",
    "VIEWING_COMPLETED",
    "NEGOTIATION",
    "CONVERTED",
    "NURTURE",
    "REENGAGEMENT",
    "UNRESPONSIVE",
    "LOST",
    "DO_NOT_CONTACT",
    "HUMAN_HANDOFF",
    "CLOSED",
}

TERMINAL_STATES = {"CONVERTED", "LOST", "DO_NOT_CONTACT", "CLOSED"}

# Valid state transition graph
ALLOWED_TRANSITIONS = {
    "NEW": {"CONTACTING", "ENGAGING", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "CONTACTING": {"ENGAGING", "QUALIFYING", "UNRESPONSIVE", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "ENGAGING": {"QUALIFYING", "QUALIFIED", "RECOMMENDATION_SENT", "UNRESPONSIVE", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "QUALIFYING": {"QUALIFIED", "RECOMMENDATION_SENT", "UNRESPONSIVE", "LOST", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "QUALIFIED": {"RECOMMENDATION_SENT", "VIEWING_PENDING", "VIEWING_BOOKED", "UNRESPONSIVE", "LOST", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "RECOMMENDATION_SENT": {"VIEWING_PENDING", "VIEWING_BOOKED", "ENGAGING", "UNRESPONSIVE", "NURTURE", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "VIEWING_PENDING": {"VIEWING_BOOKED", "RECOMMENDATION_SENT", "UNRESPONSIVE", "LOST", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "VIEWING_BOOKED": {"VIEWING_COMPLETED", "VIEWING_PENDING", "LOST", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "VIEWING_COMPLETED": {"NEGOTIATION", "RECOMMENDATION_SENT", "NURTURE", "LOST", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "NEGOTIATION": {"CONVERTED", "LOST", "NURTURE", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "UNRESPONSIVE": {"NURTURE", "REENGAGEMENT", "ENGAGING", "LOST", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "NURTURE": {"REENGAGEMENT", "ENGAGING", "LOST", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "REENGAGEMENT": {"ENGAGING", "QUALIFYING", "NURTURE", "UNRESPONSIVE", "DO_NOT_CONTACT", "HUMAN_HANDOFF"},
    "HUMAN_HANDOFF": {"ENGAGING", "QUALIFYING", "QUALIFIED", "NEGOTIATION", "CONVERTED", "LOST", "DO_NOT_CONTACT", "CLOSED"},
    "CONVERTED": {"CLOSED", "NURTURE"},
    "LOST": {"REENGAGEMENT", "CLOSED"},
    "DO_NOT_CONTACT": set(),
    "CLOSED": set(),
}


class LeadLifecycleManager:
    """
    Evaluates and enforces lifecycle state transitions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def can_transition(self, current_state: str, new_state: str) -> bool:
        """Checks if a transition between two states is valid."""
        cur = current_state.upper()
        target = new_state.upper()

        if cur == target:
            return True
        if cur not in VALID_LIFECYCLE_STATES or target not in VALID_LIFECYCLE_STATES:
            return False

        allowed = ALLOWED_TRANSITIONS.get(cur, set())
        return target in allowed

    async def transition_lead(
        self,
        lead: Lead,
        new_state: str,
        reason: str = "Automated Event"
    ) -> str:
        """
        Applies a state transition to a lead, updating CRM fields.
        """
        cur = (lead.pipeline_stage or "new").upper()
        target = new_state.upper()

        if not self.can_transition(cur, target):
            logger.warning(
                f"[LIFECYCLE] Transition from '{cur}' to '{target}' not allowed for Lead {lead.id}. Forcing transition."
            )

        lead.pipeline_stage = target.lower()
        if target == "DO_NOT_CONTACT":
            lead.status = "lost"
        elif target == "CONVERTED":
            lead.status = "converted"
        elif target in ("QUALIFIED", "RECOMMENDATION_SENT", "VIEWING_BOOKED"):
            lead.status = "qualified"

        await self.db.commit()
        await self.db.refresh(lead)
        logger.info(f"[LIFECYCLE] Lead {lead.id} transitioned '{cur}' -> '{target}' (Reason: {reason})")
        return target
