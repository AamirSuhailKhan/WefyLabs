"""
SLA Monitoring & Breach Escalation Engine
=========================================
Manages tenant-configurable SLA policies, tracks active response timers,
detects breaches in real-time, and creates escalation audit logs.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.models.crm_intelligence_models import SlaPolicy, SlaInstance, SlaBreach
from app.models.lead import Lead

logger = logging.getLogger(__name__)

class SlaMonitoringEngine:
    """
    Evaluates and enforces CRM Service Level Agreements.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_sla_instance(
        self,
        organization_id: str,
        lead_id: str,
        sla_type: str = "FIRST_RESPONSE",
        target_minutes: int = 15,
        broker_id: Optional[str] = None
    ) -> SlaInstance:
        """
        Starts an active SLA timer for a lead action.
        """
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(minutes=target_minutes)

        instance = SlaInstance(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=lead_id,
            broker_id=broker_id,
            sla_type=sla_type,
            target_deadline_utc=deadline,
            status="RUNNING"
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        logger.info(f"[SLA] Created {sla_type} SLA for Lead {lead_id} (Deadline: {deadline.isoformat()}).")
        return instance

    async def check_and_record_breaches(self, organization_id: Optional[str] = None) -> List[SlaBreach]:
        """
        Scans all running SLA instances where target_deadline_utc <= now and records breaches.
        """
        now = datetime.now(timezone.utc)
        conditions = [
            SlaInstance.status == "RUNNING",
            SlaInstance.target_deadline_utc <= now
        ]
        if organization_id:
            conditions.append(SlaInstance.organization_id == organization_id)

        stmt = select(SlaInstance).where(and_(*conditions)).limit(100)
        res = await self.db.execute(stmt)
        overdue_instances = res.scalars().all()

        recorded_breaches: List[SlaBreach] = []

        for inst in overdue_instances:
            inst.status = "BREACHED"
            inst_deadline = inst.target_deadline_utc if inst.target_deadline_utc.tzinfo else inst.target_deadline_utc.replace(tzinfo=timezone.utc)
            overdue_mins = int((now - inst_deadline).total_seconds() // 60)

            breach = SlaBreach(
                id=str(uuid.uuid4()),
                organization_id=inst.organization_id,
                lead_id=inst.lead_id,
                broker_id=inst.broker_id,
                instance_id=inst.id,
                sla_type=inst.sla_type,
                target_deadline_utc=inst.target_deadline_utc,
                breached_at_utc=now,
                overdue_minutes=max(1, overdue_mins),
                escalation_sent=True
            )
            self.db.add(breach)
            recorded_breaches.append(breach)

        if recorded_breaches:
            await self.db.commit()
            logger.warning(f"[SLA] Recorded {len(recorded_breaches)} SLA breach(es).")

        return recorded_breaches

    async def mark_sla_met(self, lead_id: str, sla_type: str) -> bool:
        """
        Marks an active SLA timer as successfully met before deadline.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(SlaInstance)
            .where(
                and_(
                    SlaInstance.lead_id == lead_id,
                    SlaInstance.sla_type == sla_type,
                    SlaInstance.status == "RUNNING"
                )
            )
            .values(status="MET", completed_at=now)
        )
        res = await self.db.execute(stmt)
        await self.db.commit()
        return res.rowcount > 0
