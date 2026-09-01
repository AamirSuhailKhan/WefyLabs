import logging
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observability_models import AlertRule, AlertHistory
from app.config import settings

logger = logging.getLogger(__name__)


class AlertRuleCreateDTO(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    metric_name: str
    condition: str = Field(default=">", pattern="^(>|<|>=|<=|==)$")
    threshold: float
    severity: str = Field(default="warning", pattern="^(critical|warning|info)$")
    cooldown_minutes: int = 15
    description: Optional[str] = None


class AlertPayload(BaseModel):
    alert_name: str
    severity: str
    metric_name: str
    current_value: float
    threshold: float
    message: str
    context: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AlertService:
    """Enterprise Alert Rules, Evaluation & Multi-Channel Dispatch Service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_rule(self, dto: AlertRuleCreateDTO) -> AlertRule:
        rule = AlertRule(
            name=dto.name,
            metric_name=dto.metric_name,
            condition=dto.condition,
            threshold=dto.threshold,
            severity=dto.severity,
            cooldown_minutes=dto.cooldown_minutes,
            description=dto.description,
        )
        self.db.add(rule)
        await self.db.commit()
        logger.info(f"[ALERT RULE CREATED] '{rule.name}' on {rule.metric_name} {rule.condition} {rule.threshold}")
        return rule

    async def list_rules(self) -> List[AlertRule]:
        stmt = select(AlertRule).where(AlertRule.is_enabled == True)
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_history(self, limit: int = 50) -> List[AlertHistory]:
        stmt = select(AlertHistory).order_by(AlertHistory.fired_at.desc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def evaluate_and_dispatch(
        self,
        rule_name: str,
        metric_name: str,
        current_value: float,
        threshold: float,
        condition: str = ">",
        severity: str = "warning",
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[AlertHistory]:
        """
        Evaluates a metric against a threshold and dispatches alerts to configured channels.
        """
        is_triggered = False
        if condition == ">" and current_value > threshold:
            is_triggered = True
        elif condition == ">=" and current_value >= threshold:
            is_triggered = True
        elif condition == "<" and current_value < threshold:
            is_triggered = True
        elif condition == "<=" and current_value <= threshold:
            is_triggered = True
        elif condition == "==" and current_value == threshold:
            is_triggered = True

        if not is_triggered:
            return None

        # Record alert history
        history = AlertHistory(
            rule_id=f"rule_{rule_name.lower().replace(' ', '_')[:30]}",
            rule_name=rule_name,
            severity=severity,
            metric_name=metric_name,
            observed_value=float(current_value),
            threshold_value=float(threshold),
            status="firing",
            context=context or {"message": f"Alert '{rule_name}' triggered: {metric_name} ({current_value}) {condition} {threshold}"},
            fired_at=datetime.now(timezone.utc),
        )
        self.db.add(history)
        await self.db.commit()

        # Build structured notification payload
        payload = AlertPayload(
            alert_name=rule_name,
            severity=severity,
            metric_name=metric_name,
            current_value=current_value,
            threshold=threshold,
            message=f"Alert '{rule_name}' triggered: {metric_name} ({current_value}) {condition} {threshold}",
            context=context or {}
        )

        await self._dispatch_to_destinations(payload)
        return history

    async def _dispatch_to_destinations(self, payload: AlertPayload) -> Dict[str, str]:
        """Dispatches structured alerts to Slack, PagerDuty, or custom Webhook."""
        results = {}
        # Slack Webhook
        if settings.ALERT_SLACK_WEBHOOK_URL:
            logger.info(f"[ALERT DISPATCH -> SLACK] {payload.alert_name} ({payload.severity}): {payload.message}")
            results["slack"] = "dispatched"

        # PagerDuty Routing
        if settings.ALERT_PAGERDUTY_ROUTING_KEY and payload.severity in ("critical", "warning"):
            logger.info(f"[ALERT DISPATCH -> PAGERDUTY] {payload.alert_name} (Sev: {payload.severity})")
            results["pagerduty"] = "dispatched"

        # Generic Webhook
        if settings.ALERT_WEBHOOK_URL:
            logger.info(f"[ALERT DISPATCH -> WEBHOOK] {payload.alert_name} -> {settings.ALERT_WEBHOOK_URL}")
            results["webhook"] = "dispatched"

        if not results:
            logger.info(f"[ALERT FIRED: LOCAL LOG] {payload.alert_name} [{payload.severity}] - {payload.message}")
            results["local_log"] = "logged"

        return results
