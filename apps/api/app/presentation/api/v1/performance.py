import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.services.broker_performance_service import BrokerPerformanceService

router = APIRouter(prefix="/performance", tags=["Salesforce CRM Analytics Performance Dashboard"])

@router.get("/broker")
async def get_broker_performance_endpoint(
    current_broker: Broker = Depends(get_current_broker)
):
    """Returns individual broker performance metrics, quota attainment %, and AI coaching skill gaps."""
    perf = BrokerPerformanceService.calculate_broker_performance(current_broker.id, current_broker.name or "Broker")
    return {
        "broker_id": str(perf.broker_id),
        "broker_name": perf.broker_name,
        "period": perf.period,
        "revenue_closed": perf.revenue_closed,
        "commission_earned": perf.commission_earned,
        "monthly_quota_target": perf.monthly_quota_target,
        "quota_attainment_pct": perf.quota_attainment_pct,
        "deals_closed_count": perf.deals_closed_count,
        "conversion_rate_pct": perf.conversion_rate_pct,
        "avg_response_time_mins": perf.avg_response_time_mins,
        "avg_deal_size": perf.avg_deal_size,
        "office_rank": perf.office_rank,
        "regional_rank": perf.regional_rank,
        "coaching_recommendations": [
            {
                "title": c.title,
                "category": c.category,
                "recommendation": c.recommendation,
                "impact_level": c.impact_level
            } for c in perf.coaching_recommendations
        ]
    }

@router.get("/team")
async def get_team_leaderboard_endpoint(
    current_broker: Broker = Depends(get_current_broker)
):
    """Returns office and regional leaderboards for manager dashboards."""
    leaderboard = BrokerPerformanceService.get_regional_leaderboard()
    return {
        "leaderboard": [
            {
                "rank": l.rank,
                "broker_name": l.broker_name,
                "office_name": l.office_name,
                "revenue_closed": l.revenue_closed,
                "deals_count": l.deals_count
            } for l in leaderboard
        ]
    }
