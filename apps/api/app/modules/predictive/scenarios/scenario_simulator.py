"""
Non-Destructive What-If Revenue Scenario Simulator
===================================================
Simulates the business impact of conversion rate changes, response time speedups,
and deal volume adjustments without modifying production CRM records.
"""

import logging
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.lead import Lead
from app.models.predictive_models import ForecastScenarioRecord

logger = logging.getLogger(__name__)

DEFAULT_COMMISSION_RATE = 0.02

class ScenarioSimulator:
    """
    Evaluates What-If scenarios on copies of pipeline feature aggregates.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def simulate_scenario(
        self,
        organization_id: str,
        scenario_name: str,
        conversion_rate_delta_pct: float = 0.0,
        response_time_reduction_pct: float = 0.0,
        lead_volume_delta_pct: float = 0.0,
        average_deal_size_delta_pct: float = 0.0
    ) -> ForecastScenarioRecord:
        """
        Runs mathematical simulation of parameter changes over active pipeline baseline.
        """
        # 1. Compute baseline pipeline revenue
        stmt = select(Lead).where(
            and_(
                Lead.deleted_at == None,
                Lead.pipeline_stage.notin_(["closed_won", "closed_lost", "lost"])
            )
        )
        res = await self.db.execute(stmt)
        leads = res.scalars().all()

        baseline_pipeline = sum([float(l.budget_max or 2_000_000.0) for l in leads]) or 10_000_000.0
        baseline_conversion_rate = 0.25
        baseline_revenue = baseline_pipeline * baseline_conversion_rate

        # 2. Compute simulated factors
        # Faster response times increase effective conversion (+0.1% per 1% speedup)
        response_lift = (response_time_reduction_pct / 100.0) * 0.10
        new_conversion_rate = min(0.90, max(0.05, baseline_conversion_rate + (conversion_rate_delta_pct / 100.0) + response_lift))

        volume_multiplier = 1.0 + (lead_volume_delta_pct / 100.0)
        deal_size_multiplier = 1.0 + (average_deal_size_delta_pct / 100.0)

        simulated_pipeline = baseline_pipeline * volume_multiplier * deal_size_multiplier
        simulated_revenue = simulated_pipeline * new_conversion_rate

        revenue_delta = simulated_revenue - baseline_revenue
        commission_delta = revenue_delta * DEFAULT_COMMISSION_RATE

        scenario = ForecastScenarioRecord(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            scenario_name=scenario_name,
            conversion_rate_delta_pct=conversion_rate_delta_pct,
            response_time_reduction_pct=response_time_reduction_pct,
            lead_volume_delta_pct=lead_volume_delta_pct,
            average_deal_size_delta_pct=average_deal_size_delta_pct,
            baseline_revenue_aed=round(baseline_revenue, 2),
            simulated_revenue_aed=round(simulated_revenue, 2),
            revenue_delta_aed=round(revenue_delta, 2),
            projected_commission_delta_aed=round(commission_delta, 2)
        )
        self.db.add(scenario)
        await self.db.commit()
        await self.db.refresh(scenario)
        logger.info(f"[SIMULATOR] Scenario '{scenario_name}': Simulated revenue change {revenue_delta:+,.2f} AED.")
        return scenario
