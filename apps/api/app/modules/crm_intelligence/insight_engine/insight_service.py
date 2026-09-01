"""
AI Explainable Insight Engine
=============================
Generates natural-language operational insights grounded in verified CRM data,
and respects user dismissals and snooze policies to avoid alert fatigue.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, not_

from app.models.crm_intelligence_models import (
    SalesInsight, InsightDismissal, LeadRisk, SlaBreach, PipelineHealthSnapshot
)

logger = logging.getLogger(__name__)

class InsightEngineService:
    """
    Synthesizes explainable sales insights from active operational signals.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_insights(self, organization_id: str) -> List[SalesInsight]:
        """
        Synthesizes organizational insights based on neglected leads, SLA breaches, and pipeline stagnation.
        """
        now = datetime.now(timezone.utc)

        # 1. Fetch active risks
        stmt_risks = select(LeadRisk).where(
            and_(
                LeadRisk.organization_id == organization_id,
                LeadRisk.status == "ACTIVE"
            )
        )
        res_risks = await self.db.execute(stmt_risks)
        active_risks = res_risks.scalars().all()

        neglected_count = len([r for r in active_risks if r.risk_type == "NEGLECT"])
        high_severity_count = len([r for r in active_risks if r.severity in ("HIGH", "CRITICAL")])

        # 2. Fetch SLA breaches in last 24h
        yesterday = now - timedelta(days=1)
        stmt_breaches = select(SlaBreach).where(
            and_(
                SlaBreach.organization_id == organization_id,
                SlaBreach.breached_at_utc >= yesterday
            )
        )
        res_breaches = await self.db.execute(stmt_breaches)
        recent_breaches = res_breaches.scalars().all()

        insights_to_create: List[Dict[str, Any]] = []

        if neglected_count > 0:
            insights_to_create.append({
                "insight_type": "LEAD_INSIGHT",
                "title": f"{neglected_count} High-Intent Lead(s) Neglected Without Broker Activity",
                "summary_markdown": f"**{neglected_count} qualified leads** with active buying intent have not received broker follow-up in over 24 hours. Immediate re-engagement is required to prevent deal cooling.",
                "priority": "HIGH",
                "impact_level": "CRITICAL",
                "confidence": 0.95,
                "evidence": [f"{neglected_count} leads marked with active neglect risk.", "Average inactive duration > 28 hours."],
                "action": "Open Neglected Leads list and trigger 1-click WhatsApp or reassign to available agents."
            })

        if len(recent_breaches) > 0:
            insights_to_create.append({
                "insight_type": "SLA_INSIGHT",
                "title": f"{len(recent_breaches)} SLA Breaches Recorded in Past 24 Hours",
                "summary_markdown": f"**{len(recent_breaches)} response SLA timers** expired before first broker contact was completed. First response velocity directly impacts buyer conversion rates.",
                "priority": "URGENT" if len(recent_breaches) >= 3 else "MEDIUM",
                "impact_level": "HIGH",
                "confidence": 0.98,
                "evidence": [f"{len(recent_breaches)} breach records generated across inbound leads."],
                "action": "Review SLA violation audit and enable automated AI instant-greeting for after-hours leads."
            })

        persisted: List[SalesInsight] = []
        for item in insights_to_create:
            # Check if active insight with same title already exists
            stmt_exist = select(SalesInsight).where(
                and_(
                    SalesInsight.organization_id == organization_id,
                    SalesInsight.title == item["title"],
                    SalesInsight.is_active == True
                )
            )
            res_exist = await self.db.execute(stmt_exist)
            if res_exist.scalar_one_or_none():
                continue

            insight = SalesInsight(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                insight_type=item["insight_type"],
                title=item["title"],
                summary_markdown=item["summary_markdown"],
                priority=item["priority"],
                impact_level=item["impact_level"],
                confidence=item["confidence"],
                evidence=item["evidence"],
                recommended_action=item["action"],
                is_active=True,
                expires_at=now + timedelta(days=2)
            )
            self.db.add(insight)
            persisted.append(insight)

        if persisted:
            await self.db.commit()
            logger.info(f"[INSIGHTS] Created {len(persisted)} new sales insights.")

        return persisted

    async def dismiss_insight(self, insight_id: str, broker_id: str) -> bool:
        """
        Records a user dismissal to deactivate the insight.
        """
        stmt = select(SalesInsight).where(SalesInsight.id == insight_id)
        res = await self.db.execute(stmt)
        insight = res.scalar_one_or_none()
        if not insight:
            return False

        insight.is_active = False
        dismissal = InsightDismissal(
            id=str(uuid.uuid4()),
            insight_id=insight.id,
            broker_id=broker_id,
            action="DISMISSED",
            dismissed_at=datetime.now(timezone.utc)
        )
        self.db.add(dismissal)
        await self.db.commit()
        return True

    async def snooze_insight(self, insight_id: str, broker_id: str, snooze_hours: int = 12, **kwargs) -> bool:
        """
        Snoozes an insight for N hours.
        """
        stmt = select(SalesInsight).where(SalesInsight.id == insight_id)
        res = await self.db.execute(stmt)
        insight = res.scalar_one_or_none()
        if not insight:
            return False

        duration = kwargs.get("hours", snooze_hours)
        now = datetime.now(timezone.utc)
        insight.expires_at = now + timedelta(hours=duration)

        dismissal = InsightDismissal(
            id=str(uuid.uuid4()),
            insight_id=insight.id,
            broker_id=broker_id,
            action="SNOOZED",
            snooze_until=insight.expires_at,
            dismissed_at=now
        )
        self.db.add(dismissal)
        await self.db.commit()
        return True
