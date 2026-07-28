import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.follow_up import FollowUp

logger = logging.getLogger(__name__)

async def schedule_followup_sequence(db: AsyncSession, lead: Lead) -> List[FollowUp]:
    """
    Schedules 3 follow-up messages for a lead at T+24h, T+48h, and T+72h intervals.
    """
    # Fetch broker details
    broker_stmt = select(Broker).where(Broker.id == lead.broker_id)
    broker = (await db.execute(broker_stmt)).scalars().first()
    
    broker_name = broker.name if broker else "our team"
    lead_name = lead.name or "there"
    property_type = (lead.property_type or "property").upper()
    location = lead.preferred_locations[0] if lead.preferred_locations else "Bengaluru"
    
    now = datetime.now(timezone.utc)
    
    follow_up_1 = FollowUp(
        lead_id=lead.id,
        sequence_number=1,
        scheduled_at=now + timedelta(hours=24),
        status="scheduled",
        message=f"Hi {lead_name}, just checking in. Are you still looking for {property_type} in {location}? Reply YES to continue."
    )
    
    follow_up_2 = FollowUp(
        lead_id=lead.id,
        sequence_number=2,
        scheduled_at=now + timedelta(hours=48),
        status="scheduled",
        message=f"Hi, {broker_name} has some new listings matching your budget. Interested in a quick call?"
    )
    
    follow_up_3 = FollowUp(
        lead_id=lead.id,
        sequence_number=3,
        scheduled_at=now + timedelta(hours=72),
        status="scheduled",
        message=f"Last follow-up from {broker_name}'s office. If you're no longer looking, just reply STOP."
    )
    
    db.add_all([follow_up_1, follow_up_2, follow_up_3])
    await db.commit()
    await db.refresh(follow_up_1)
    await db.refresh(follow_up_2)
    await db.refresh(follow_up_3)
    
    logger.info(f"[FollowUp Service] Scheduled 3 follow-ups for Lead {lead.id}")
    return [follow_up_1, follow_up_2, follow_up_3]

async def cancel_pending_followups(db: AsyncSession, lead_id: uuid.UUID) -> int:
    """
    Cancels all scheduled follow-ups for a specific lead.
    Returns the number of cancelled follow-ups.
    """
    stmt = (
        update(FollowUp)
        .where(
            FollowUp.lead_id == lead_id,
            FollowUp.status == "scheduled"
        )
        .values(status="cancelled")
    )
    result = await db.execute(stmt)
    await db.commit()
    
    cancelled_count = result.rowcount
    if cancelled_count > 0:
        logger.info(f"[FollowUp Service] Cancelled {cancelled_count} pending follow-ups for Lead {lead_id}")
    return cancelled_count
