"""
Expected Close Date & Sales Cycle Duration Predictor
=====================================================
Estimates expected conversion date, realistic time range intervals,
and historical stage velocities by market segment.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lead import Lead
from app.models.predictive_models import SalesCyclePredictionSnapshot

logger = logging.getLogger(__name__)

# Typical sales cycle duration by current pipeline stage (in days)
STAGE_REMAINING_DAYS_BENCHMARK: Dict[str, int] = {
    "new": 30,
    "contacted": 25,
    "qualified": 20,
    "meeting": 14,
    "viewing": 12,
    "negotiation": 7,
    "offer": 4,
    "closed_won": 0,
    "closed_lost": 0
}

class CloseDatePredictionService:
    """
    Predicts expected close date and range intervals for opportunities and leads.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def predict_close_date(
        self,
        lead_id: str,
        organization_id: str
    ) -> SalesCyclePredictionSnapshot:
        """
        Calculates expected close date, earliest/latest bounds, and market segment velocity.
        """
        import uuid as _uuid
        try:
            l_pk = _uuid.UUID(str(lead_id))
        except Exception:
            l_pk = lead_id

        stmt = select(Lead).where(Lead.id == l_pk)
        res = await self.db.execute(stmt)
        lead = res.scalar_one_or_none()
        if not lead:
            raise ValueError(f"Lead '{lead_id}' not found.")

        now = datetime.now(timezone.utc)
        stage = (lead.pipeline_stage or "new").lower()
        base_days = STAGE_REMAINING_DAYS_BENCHMARK.get(stage, 21)

        # Adjustment based on lead score / engagement
        if lead.score == "hot":
            adjusted_days = max(3, int(base_days * 0.75))
            confidence = 0.90
        elif lead.score == "cold":
            adjusted_days = int(base_days * 1.40)
            confidence = 0.65
        else:
            adjusted_days = base_days
            confidence = 0.80

        # Segment determination
        budget = float(lead.budget_max or 2_000_000.0)
        segment = "ultra_luxury" if budget >= 10_000_000.0 else "luxury" if budget >= 3_000_000.0 else "mid_market"

        expected_date = now + timedelta(days=adjusted_days)
        earliest_date = now + timedelta(days=max(1, adjusted_days - max(3, int(adjusted_days * 0.35))))
        latest_date = now + timedelta(days=adjusted_days + max(5, int(adjusted_days * 0.45)))

        snapshot = SalesCyclePredictionSnapshot(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=str(lead.id),
            expected_sales_cycle_days=adjusted_days,
            expected_close_date_utc=expected_date,
            range_earliest_date_utc=earliest_date,
            range_latest_date_utc=latest_date,
            confidence=confidence,
            market_segment=segment
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        logger.info(f"[SALES_CYCLE] Lead {lead_id} expected close date: {expected_date.strftime('%Y-%m-%d')} ({adjusted_days} days).")
        return snapshot
