from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.alerts.service.alert_service import AlertService, AlertRuleCreateDTO

router = APIRouter(prefix="/v1/alerts", tags=["Alerting System"])


@router.get("/rules", response_model=APIResponse)
async def list_alert_rules(
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = AlertService(db)
    rules = await svc.list_rules()
    return create_success_response(data=[
        {
            "id": r.id,
            "name": r.name,
            "metric_name": r.metric_name,
            "condition": r.condition,
            "threshold": r.threshold,
            "severity": r.severity,
            "cooldown_minutes": r.cooldown_minutes,
        } for r in rules
    ])


@router.post("/rules", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    dto: AlertRuleCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = AlertService(db)
    rule = await svc.create_rule(dto)
    return create_success_response(data={"id": rule.id, "name": rule.name})


@router.get("/history", response_model=APIResponse)
async def list_alert_history(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = AlertService(db)
    items = await svc.list_history(limit=limit)
    return create_success_response(data=[
        {
            "id": h.id,
            "rule_name": h.rule_name,
            "severity": h.severity,
            "observed_value": h.observed_value,
            "threshold_value": h.threshold_value,
            "status": h.status,
            "fired_at": h.fired_at,
        } for h in items
    ])
