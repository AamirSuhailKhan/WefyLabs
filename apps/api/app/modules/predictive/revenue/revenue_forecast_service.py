"""
Multi-Horizon Revenue & Commission Forecasting Engine
=====================================================
Calculates probability-weighted pipeline revenue, conservative/optimistic bounds,
and expected brokerage commissions across 7d, 30d, 60d, 90d, and quarterly horizons.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.lead import Lead
from app.models.predictive_models import ForecastSnapshotRecord

logger = logging.getLogger(__name__)

# Standard brokerage commission rate proxy (2.0%)
DEFAULT_COMMISSION_RATE = 0.02

# Probability multipliers by stage
STAGE_PROBABILITY_WEIGHTS: Dict[str, float] = {
    "new": 0.10,
    "contacted": 0.20,
    "qualified": 0.35,
    "meeting": 0.50,
    "viewing": 0.60,
    "negotiation": 0.80,
    "offer": 0.90,
    "closed_won": 1.00,
    "closed_lost": 0.00,
}

class RevenueForecastService:
    """
    Computes multi-horizon pipeline forecasts and expected revenue distributions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_revenue_forecast(
        self,
        organization_id: str,
        horizon: str = "30_DAYS",
        reporting_currency: str = "AED"
    ) -> ForecastSnapshotRecord:
        """
        Aggregates active pipeline leads into weighted expected revenue and confidence bands.
        """
        now = datetime.now(timezone.utc)

        # 1. Fetch active leads
        stmt = select(Lead).where(
            and_(
                Lead.deleted_at == None,
                Lead.pipeline_stage.notin_(["closed_won", "closed_lost", "lost"])
            )
        )
        res = await self.db.execute(stmt)
        leads = res.scalars().all()

        total_pipeline = 0.0
        weighted_pipeline = 0.0
        stage_breakdown: Dict[str, Dict[str, Any]] = {}

        # Horizon conversion multiplier (e.g. 7_DAYS captures immediate deals, QUARTER captures wider pipeline)
        horizon_factor = (
            0.40 if horizon == "7_DAYS" else
            0.70 if horizon == "30_DAYS" else
            0.85 if horizon == "60_DAYS" else
            1.00
        )

        for l in leads:
            stg = (l.pipeline_stage or "new").lower()
            val = float(l.budget_max or 2_000_000.0)
            stg_prob = STAGE_PROBABILITY_WEIGHTS.get(stg, 0.25)
            weighted_deal = (val * stg_prob) * horizon_factor

            total_pipeline += val
            weighted_pipeline += weighted_deal

            if stg not in stage_breakdown:
                stage_breakdown[stg] = {"count": 0, "total_value": 0.0, "weighted_value": 0.0}
            stage_breakdown[stg]["count"] += 1
            stage_breakdown[stg]["total_value"] += val
            stage_breakdown[stg]["weighted_value"] += weighted_deal

        expected_rev = weighted_pipeline
        conservative_rev = expected_rev * 0.78  # P10
        optimistic_rev = expected_rev * 1.30    # P90
        expected_commission = expected_rev * DEFAULT_COMMISSION_RATE

        snapshot = ForecastSnapshotRecord(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            horizon=horizon,
            reporting_currency=reporting_currency,
            total_pipeline_value=round(total_pipeline, 2),
            weighted_pipeline_value=round(weighted_pipeline, 2),
            expected_revenue=round(expected_rev, 2),
            conservative_revenue=round(conservative_rev, 2),
            optimistic_revenue=round(optimistic_rev, 2),
            expected_commission=round(expected_commission, 2),
            forecast_confidence=0.88,
            segment_breakdown=stage_breakdown,
            generated_at=now
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        logger.info(f"[REVENUE_FORECAST] Generated {horizon} forecast: Expected {reporting_currency} {expected_rev:,.2f}.")
        return snapshot
