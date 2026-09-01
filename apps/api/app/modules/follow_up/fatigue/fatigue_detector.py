"""
Contact Fatigue & Frequency Detector
====================================
Tracks unanswered follow-up counts, calculates fatigue scores, and enforces
anti-spam suppression rules.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.follow_up_models import ContactFatigue, FollowUpPolicy

logger = logging.getLogger(__name__)

class FatigueDetector:
    """
    Evaluates lead communication fatigue and consecutive unanswered attempts.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_fatigue(self, lead_id: str, organization_id: str) -> ContactFatigue:
        """Loads or creates a fatigue tracking record for a lead."""
        stmt = select(ContactFatigue).where(ContactFatigue.lead_id == lead_id)
        res = await self.db.execute(stmt)
        record = res.scalar_one_or_none()

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
            await self.db.commit()
            await self.db.refresh(record)

        return record

    async def evaluate_fatigue(
        self,
        lead_id: str,
        organization_id: str,
        policy: FollowUpPolicy
    ) -> Tuple[bool, float, str]:
        """
        Calculates fatigue score and returns (is_suppressed, fatigue_score, reason).
        """
        record = await self.get_or_create_fatigue(lead_id, organization_id)

        # Check consecutive no replies
        max_no_reply = policy.max_consecutive_no_reply if policy else 3
        if record.consecutive_no_replies >= max_no_reply:
            score = 1.0
            record.current_fatigue_score = score
            record.is_suppressed = True
            await self.db.commit()
            return True, score, f"Reached maximum consecutive unanswered attempts ({record.consecutive_no_replies}/{max_no_reply})"

        # Calculate score (e.g. 0.33 per unanswered msg)
        score = min(1.0, record.consecutive_no_replies / float(max_no_reply))
        record.current_fatigue_score = score
        await self.db.commit()

        return False, score, "Fatigue within acceptable threshold"

    async def record_outbound_sent(self, lead_id: str, organization_id: str) -> None:
        """Increments outbound count and consecutive unanswered count."""
        record = await self.get_or_create_fatigue(lead_id, organization_id)
        record.total_messages_sent += 1
        record.consecutive_no_replies += 1
        record.last_contacted_at = datetime.now(timezone.utc)
        await self.db.commit()

    async def record_inbound_response(self, lead_id: str, organization_id: str) -> None:
        """Resets consecutive unanswered count and clears suppression."""
        record = await self.get_or_create_fatigue(lead_id, organization_id)
        record.consecutive_no_replies = 0
        record.current_fatigue_score = 0.0
        record.is_suppressed = False
        record.last_responded_at = datetime.now(timezone.utc)
        record.suppressed_until = None
        await self.db.commit()
        logger.info(f"[FATIGUE] Inbound reply received for Lead {lead_id}. Fatigue reset to 0.0.")
