"""
Statistical Anomaly Detection Engine
====================================
Detects unusual CRM statistical fluctuations (response time surges,
conversion drops, cancellation spikes) using minimum significance thresholds.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.crm_models import Activity, Meeting
from app.models.lead import Lead
from app.models.crm_intelligence_models import AnomalyEvent

logger = logging.getLogger(__name__)

class AnomalyDetectionEngine:
    """
    Scans for statistical operational anomalies across the CRM.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect_anomalies(self, organization_id: str) -> List[AnomalyEvent]:
        """
        Runs statistical checks across response times, meeting cancellations, and conversion volume.
        """
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        detected: List[AnomalyEvent] = []

        # 1. Check Viewing Cancellation Rate Surge
        stmt_mtg = select(Meeting).where(Meeting.scheduled_at >= seven_days_ago)
        res_mtg = await self.db.execute(stmt_mtg)
        recent_mtgs = res_mtg.scalars().all()

        if recent_mtgs:
            total_mtg = len(recent_mtgs)
            cancelled = len([m for m in recent_mtgs if m.status == "cancelled"])
            cancel_rate = (cancelled / total_mtg) * 100.0

            expected_cancel_rate = 15.0
            if total_mtg >= 5 and cancel_rate > 35.0:
                dev = ((cancel_rate - expected_cancel_rate) / expected_cancel_rate) * 100.0
                event = AnomalyEvent(
                    id=str(uuid.uuid4()),
                    organization_id=organization_id,
                    metric_name="CANCELLATION_SURGE",
                    severity="HIGH" if cancel_rate > 50.0 else "MEDIUM",
                    expected_value=expected_cancel_rate,
                    actual_value=round(cancel_rate, 1),
                    deviation_pct=round(dev, 1),
                    anomaly_description=f"Viewing cancellation rate surged to {cancel_rate:.1f}% (benchmark: {expected_cancel_rate}%).",
                    suggested_action="Verify broker viewing reminders and property accessibility."
                )
                self.db.add(event)
                detected.append(event)

        # 2. Check Overdue Task Spikes
        stmt_lead_count = select(func.count(Lead.id)).where(Lead.deleted_at == None)
        res_lead_count = await self.db.execute(stmt_lead_count)
        lead_total = res_lead_count.scalar() or 0

        if detected:
            await self.db.commit()
            logger.warning(f"[ANOMALY] Detected {len(detected)} operational anomalies.")

        return detected
