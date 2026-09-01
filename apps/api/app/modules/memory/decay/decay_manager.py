"""
Memory Decay & Freshness Manager
================================
Calculates recency decay curves and marks unconfirmed time-sensitive memories as STALE or EXPIRED.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.models.memory_models import MemoryRecord

logger = logging.getLogger(__name__)

# Days before unconfirmed memory decays to STALE status
DECAY_HALF_LIFE_DAYS: Dict[str, int] = {
    "TIMELINE": 30,
    "INTENT": 45,
    "BUDGET": 90,
    "PREFERENCE": 180,
    "CONSTRAINT": 180,
    "LOCATION": 180,
    "NEGATIVE_PREFERENCE": 180,
    "IDENTITY": 365,
    "COMMUNICATION_PREFERENCE": 365
}

class DecayManager:
    """
    Evaluates memory freshness and runs periodic decay transitions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_stale_memories(self, organization_id: Optional[str] = None) -> List[MemoryRecord]:
        """
        Queries ACTIVE memories that exceed their freshness half-life and transitions them to STALE.
        """
        now = datetime.now(timezone.utc)
        stmt = select(MemoryRecord).where(MemoryRecord.status == "ACTIVE")
        if organization_id:
            stmt = stmt.where(MemoryRecord.organization_id == organization_id)

        res = await self.db.execute(stmt)
        records = list(res.scalars().all())
        stale_records: List[MemoryRecord] = []

        for rec in records:
            half_life = DECAY_HALF_LIFE_DAYS.get(rec.memory_type, 180)
            last_checked = rec.last_confirmed_at or rec.updated_at or rec.created_at
            if last_checked and (now - last_checked).days > half_life:
                rec.status = "STALE"
                stale_records.append(rec)

        if stale_records:
            await self.db.commit()
            logger.info(f"[DECAY_MANAGER] Transitioned {len(stale_records)} memory record(s) to STALE.")
        return stale_records
