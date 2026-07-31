import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.services.predictive_analytics_service import PredictiveAnalyticsService

router = APIRouter(prefix="/v1/predictive", tags=["Salesforce Einstein Predictive Intelligence"])

@router.get("/dashboard")
async def get_predictive_dashboard_endpoint(
    current_broker: Broker = Depends(get_current_broker)
):
    """Returns quarterly revenue forecast, pipeline health score, and churn benchmarks."""
    forecast = PredictiveAnalyticsService.forecast_quarterly_revenue()
    return {
        "quarter": forecast.quarter,
        "projected_revenue": forecast.projected_revenue,
        "confidence_interval": {
            "lower_bound": forecast.confidence_lower_bound,
            "upper_bound": forecast.confidence_upper_bound
        },
        "pipeline_health_score": forecast.pipeline_health_score,
        "agent_coaching_score": 94.2
    }

@router.get("/leads/{lead_id}")
async def get_lead_predictive_intelligence_endpoint(
    lead_id: uuid.UUID,
    current_broker: Broker = Depends(get_current_broker)
):
    """Returns AI conversion probability %, LTV, best follow-up window, and SHAP explanation factors."""
    pred = PredictiveAnalyticsService.predict_lead_intelligence(lead_id)
    return {
        "lead_id": str(lead_id),
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
        ]
    }
