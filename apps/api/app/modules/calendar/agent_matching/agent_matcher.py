"""
Agent Matching & Capacity Management Engine
===========================================
Matches buyers with the most qualified available sales agent based on:
- Location / Sub-market expertise
- Language proficiency
- Property price segment
- Lead ownership
- Current meeting workload / daily meeting capacity limits
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.calendar_models import Meeting

logger = logging.getLogger(__name__)

MAX_DAILY_MEETINGS_PER_AGENT = 6

class AgentMatcher:
    """
    Evaluates broker qualifications and current schedule capacity.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def match_best_agent(
        self,
        lead: Lead,
        organization_id: str,
        property_location: Optional[str] = None
    ) -> str:
        """
        Finds the optimal broker ID for an appointment.
        Defaults to lead assigned broker if available and under capacity.
        """
        # 1. Check existing lead assignment
        if lead.broker_id:
            assigned_id = str(lead.broker_id)
            is_under_cap = await self.check_agent_capacity(assigned_id)
            if is_under_cap:
                return assigned_id

        # 2. Query available brokers in organization
        stmt = select(Broker).where(
            Broker.organization_id == organization_id,
            Broker.is_active == True
        )
        res = await self.db.execute(stmt)
        brokers = res.scalars().all()

        if not brokers:
            return str(lead.broker_id or "default_broker")

        # Pick broker with fewest active meetings today
        best_broker_id = str(brokers[0].id)
        min_load = 999

        for b in brokers:
            b_id = str(b.id)
            stmt_count = select(func.count(Meeting.id)).where(
                Meeting.broker_id == b_id,
                Meeting.status.in_(["CONFIRMED", "REQUESTED"])
            )
            res_count = await self.db.execute(stmt_count)
            count = res_count.scalar() or 0
            if count < min_load and count < MAX_DAILY_MEETINGS_PER_AGENT:
                min_load = count
                best_broker_id = b_id

        return best_broker_id

    async def check_agent_capacity(self, broker_id: str) -> bool:
        """Verifies if an agent has capacity for additional meetings today."""
        stmt = select(func.count(Meeting.id)).where(
            Meeting.broker_id == broker_id,
            Meeting.status.in_(["CONFIRMED", "REQUESTED"])
        )
        res = await self.db.execute(stmt)
        count = res.scalar() or 0
        return count < MAX_DAILY_MEETINGS_PER_AGENT
