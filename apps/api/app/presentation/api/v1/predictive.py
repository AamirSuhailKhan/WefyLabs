import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.transaction_models import DealTransaction
from app.services.predictive_analytics_service import PredictiveAnalyticsService

router = APIRouter(prefix="/predictive", tags=["Conversion Propensity Intelligence"])

@router.get("/dashboard")
async def get_predictive_dashboard_endpoint(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Returns quarterly revenue forecast and pipeline health score derived from broker data."""
    try:
        deal_stmt = select(DealTransaction).where(DealTransaction.broker_id == current_broker.id)
        deals = (await db.execute(deal_stmt)).scalars().all()
    except Exception:
        deals = []

    try:
        lead_stmt = select(Lead).where(Lead.broker_id == current_broker.id, Lead.deleted_at.is_(None))
        leads = (await db.execute(lead_stmt)).scalars().all()
    except Exception:
        leads = []

    forecast = PredictiveAnalyticsService.forecast_quarterly_revenue(deals=deals, leads=leads)
    return {
        "quarter": forecast.quarter,
        "projected_revenue": forecast.projected_revenue,
        "confidence_interval": {
            "lower_bound": forecast.confidence_lower_bound,
            "upper_bound": forecast.confidence_upper_bound
        },
        "pipeline_health_score": forecast.pipeline_health_score,
        "deals_count": forecast.deals_count,
        "calculation_basis": forecast.calculation_basis,
    }

@router.get("/leads/{lead_id}")
async def get_lead_predictive_intelligence_endpoint(
    lead_id: uuid.UUID,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Returns real feature-based conversion propensity %, LTV, best follow-up window, and attribute explanations."""
    stmt = (
        select(Lead)
        .where(
            Lead.id == lead_id,
            Lead.broker_id == current_broker.id,
            Lead.deleted_at.is_(None)
        )
        .options(selectinload(Lead.conversations))
    )
    res = await db.execute(stmt)
    lead = res.scalars().first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found or unauthorized access"
        )

    pred = PredictiveAnalyticsService.predict_lead_intelligence(lead_id=lead_id, lead=lead)
    return {
        "lead_id": str(lead_id),
        "model_version": pred.model_version,
        "conversion_probability_pct": pred.conversion_probability_pct,
        "deal_close_probability_pct": pred.deal_close_probability_pct,
        "churn_risk_pct": pred.churn_risk_pct,
        "estimated_lifetime_value": pred.estimated_lifetime_value,
        "best_followup_window": pred.best_followup_window,
        "confidence_interval": pred.confidence_interval,
        "feature_attributions": [
            {
                "feature": f.feature_name,
                "impact": f.impact_score,
                "explanation": f.description
            } for f in pred.feature_attributions
        ],
        "prediction_timestamp": pred.prediction_timestamp,
    }
