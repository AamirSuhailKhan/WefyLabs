from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.services.tableau_bi_service import TableauBIService

router = APIRouter(prefix="/v1/bi", tags=["Tableau & Salesforce Grade Executive Analytics"])

class NLQueryRequest(BaseModel):
    query: str

@router.get("/executive-summary")
async def get_executive_summary_endpoint(
    current_broker: Broker = Depends(get_current_broker)
):
    """Returns high-level C-suite Tableau BI summary metrics and automated anomaly alerts."""
    summary = TableauBIService.get_executive_summary()
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
    current_broker: Broker = Depends(get_current_broker)
):
    """Natural Language Analytics API enabling C-suite leaders to ask any business question."""
    res = TableauBIService.process_nl_analytics_query(req.query)
    return {
        "query": res.query,
        "chart_type": res.chart_type,
        "explanation_markdown": res.explanation_markdown,
        "data_points": res.data_points
    }
