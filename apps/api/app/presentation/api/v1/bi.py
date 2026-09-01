from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.services.tableau_bi_service import TableauBIService

router = APIRouter(prefix="/bi", tags=["Tableau & Salesforce Grade Executive Analytics"])

class NLQueryRequest(BaseModel):
    query: str

@router.get("/executive-summary")
async def get_executive_summary_endpoint(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Returns high-level C-suite Tableau BI summary metrics and automated anomaly alerts."""
    summary = await TableauBIService.async_get_executive_summary(db=db, broker=current_broker)
    return {
        "revenue_ytd": summary.revenue_ytd,
        "pipeline_total_value": summary.pipeline_total_value,
        "avg_customer_acquisition_cost": summary.avg_customer_acquisition_cost,
        "marketing_campaign_roi_pct": summary.marketing_campaign_roi_pct,
        "conversion_rate_overall_pct": summary.conversion_rate_overall_pct,
        "anomalies": [
            {
                "id": a.id,
                "severity": a.severity,
                "metric_name": a.metric_name,
                "description": a.anomaly_description,
                "root_cause": a.root_cause_explanation,
                "action": a.recommended_action
            } for a in summary.anomalies
        ]
    }

@router.post("/ask-nl-query")
async def ask_natural_language_analytics_endpoint(
    req: NLQueryRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Natural Language Analytics API enabling C-suite leaders to ask any business question."""
    res = await TableauBIService.async_process_nl_analytics_query(db=db, broker=current_broker, query=req.query)
    return {
        "query": res.query,
        "chart_type": res.chart_type,
        "explanation_markdown": res.explanation_markdown,
        "data_points": res.data_points
    }
