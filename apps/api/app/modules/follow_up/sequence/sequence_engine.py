"""
Adaptive Follow-Up Sequence Engine
==================================
Manages multi-step automated sequences, step advancement, and the critical invariant:
HALTS immediately upon receiving an inbound customer reply or human takeover.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.lead import Lead
from app.models.follow_up_models import (
    FollowUpSequence, FollowUpSequenceStep, FollowUpEnrollment, FollowUpExecution
)

logger = logging.getLogger(__name__)

class SequenceEngine:
    """
    Executes and monitors multi-step lead follow-up sequences.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_default_sequence(
        self,
        organization_id: str,
        lifecycle_state: str = "QUALIFYING"
    ) -> FollowUpSequence:
        """
        Retrieves the active sequence for a state, or seeds an enterprise 3-step sequence.
        """
        stmt = select(FollowUpSequence).where(
            FollowUpSequence.organization_id == organization_id,
            FollowUpSequence.target_lifecycle_state == lifecycle_state.upper(),
            FollowUpSequence.is_active == True
        )
        res = await self.db.execute(stmt)
        seq = res.scalar_one_or_none()

        if seq:
            return seq

        # Create standard 3-step enterprise sequence
        seq = FollowUpSequence(
            organization_id=organization_id,
            name=f"Standard {lifecycle_state.capitalize()} Sequence",
            description="3-step adaptive follow-up sequence with value-driven touchpoints",
            target_lifecycle_state=lifecycle_state.upper(),
            is_active=True
        )
        self.db.add(seq)
        await self.db.commit()
        await self.db.refresh(seq)

        step1 = FollowUpSequenceStep(
            sequence_id=seq.id,
            step_number=1,
            delay_hours=24,
            preferred_channel="WHATSAPP",
            reason_type="PROPERTY_RECOMMENDATION",
            message_goal="Share top verified property matches"
        )
        step2 = FollowUpSequenceStep(
            sequence_id=seq.id,
            step_number=2,
            delay_hours=48,
            preferred_channel="WHATSAPP",
            reason_type="UNANSWERED_INQUIRY",
            message_goal="Offer payment plan details & floor plans"
        )
        step3 = FollowUpSequenceStep(
            sequence_id=seq.id,
            step_number=3,
            delay_hours=72,
            preferred_channel="EMAIL",
            reason_type="REENGAGEMENT",
            message_goal="Market insights & alternative inventory"
        )
        self.db.add_all([step1, step2, step3])
        await self.db.commit()

        return seq

    async def halt_active_enrollments(
        self,
        lead_id: str,
        reason: str = "Customer Responded"
    ) -> int:
        """
        HALT INVARIANT: Immediately terminates all active sequence enrollments for a lead.
        Cancels any scheduled executions linked to the enrollment.
        """
        stmt = (
            update(FollowUpEnrollment)
            .where(
                FollowUpEnrollment.lead_id == lead_id,
                FollowUpEnrollment.status == "ACTIVE"
            )
            .values(status="HALTED_REPLY", completed_at=datetime.now(timezone.utc))
        )
        res = await self.db.execute(stmt)
        halted_count = res.rowcount

        # Cancel scheduled executions
        stmt_cancel = (
            update(FollowUpExecution)
            .where(
                FollowUpExecution.lead_id == lead_id,
                FollowUpExecution.status == "SCHEDULED"
            )
            .values(status="CANCELLED", suppression_reason=reason)
        )
        await self.db.execute(stmt_cancel)
        await self.db.commit()

        if halted_count > 0:
            logger.info(f"[SEQUENCE] Halted {halted_count} active sequences for Lead {lead_id} ({reason}).")

        return halted_count
