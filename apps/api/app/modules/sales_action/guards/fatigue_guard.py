"""
Part 21.5 — Communication Fatigue & Frequency Guard
===================================================
Tracks unified customer communication budget across all channels.
Prevents rapid-fire messaging, spam, and cross-channel harassment.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.follow_up_models import ContactFatigue, FollowUpPolicy, FollowUpExecution

logger = logging.getLogger(__name__)


class FatigueGuard:
    """
    Evaluates contact fatigue, frequency caps, and message pacing.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_fatigue(self, lead_id: str, organization_id: str) -> ContactFatigue:
        """Loads or initializes a fatigue tracking record for a lead."""
        stmt = select(ContactFatigue).where(ContactFatigue.lead_id == lead_id)
        res = await self.db.execute(stmt)
        record = res.scalars().first()

        if not record:
            record = ContactFatigue(
                lead_id=lead_id,
                organization_id=organization_id,
                total_messages_sent=0,
                consecutive_no_replies=0,
                current_fatigue_score=0.0,
                is_suppressed=False
            )
            self.db.add(record)
            await self.db.flush()

        return record

    async def evaluate_fatigue(
        self,
        lead_id: str,
        organization_id: str,
        policy: Optional[FollowUpPolicy] = None,
    ) -> Tuple[bool, float, Optional[str], bool]:
        """
        Evaluates fatigue limits.
        Returns (is_blocked, fatigue_score, reason, is_dormant_candidate).
        """
        record = await self.get_or_create_fatigue(lead_id, organization_id)
        max_no_reply = policy.max_consecutive_no_reply if policy else 3
        min_hours = policy.min_hours_between_msgs if policy else 18

        # 1. Consecutive unanswered cap
        if record.consecutive_no_replies >= max_no_reply:
            record.current_fatigue_score = 1.0
            record.is_suppressed = True
            await self.db.flush()
            reason = f"Maximum consecutive unanswered communications reached ({record.consecutive_no_replies}/{max_no_reply})."
            return True, 1.0, reason, True

        # 2. Minimum interval pacing
        stmt_last = (
            select(FollowUpExecution)
            .where(
                FollowUpExecution.lead_id == lead_id,
                FollowUpExecution.status.in_(["SENT", "DELIVERED", "READ", "DISPATCHED"])
            )
            .order_by(desc(FollowUpExecution.executed_at))
            .limit(1)
        )
        res_last = await self.db.execute(stmt_last)
        last_exec = res_last.scalars().first()

        if last_exec and last_exec.executed_at:
            delta = datetime.now(timezone.utc) - last_exec.executed_at
            if delta < timedelta(hours=min_hours):
                hours_left = min_hours - (delta.total_seconds() / 3600.0)
                reason = f"Minimum interval between messages not met. Next outreach allowed in {hours_left:.1f}h."
                score = round(min(1.0, record.consecutive_no_replies / float(max_no_reply)), 2)
                return True, score, reason, False

        score = round(min(1.0, record.consecutive_no_replies / float(max_no_reply)), 2)
        record.current_fatigue_score = score
        await self.db.flush()
        return False, score, None, False

    async def record_outbound_sent(self, lead_id: str, organization_id: str) -> None:
        """Updates fatigue counters after outbound communication."""
        record = await self.get_or_create_fatigue(lead_id, organization_id)
        record.total_messages_sent += 1
        record.consecutive_no_replies += 1
        record.last_contacted_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def record_inbound_response(self, lead_id: str, organization_id: str) -> None:
        """Resets fatigue counters upon customer inbound response."""
        record = await self.get_or_create_fatigue(lead_id, organization_id)
        record.consecutive_no_replies = 0
        record.current_fatigue_score = 0.0
        record.is_suppressed = False
        record.last_responded_at = datetime.now(timezone.utc)
        record.suppressed_until = None
        await self.db.flush()
