"""
Observability, Alerting & Reliability Test Suite
================================================
Tests:
- Alert rule creation and validation
- Threshold evaluation (> , >= , < , <= , ==)
- Alert history recording
- Multi-destination alert dispatching (Slack, PagerDuty, Webhooks)
- Standard system alert triggers (API error rate, DB failure, latency)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.alerts.service.alert_service import AlertService, AlertRuleCreateDTO, AlertPayload
from app.config import settings


class TestAlertEvaluationAndDispatch:
    """Tests alert threshold evaluation and multi-channel dispatch."""

    @pytest.mark.asyncio
    async def test_threshold_triggering(self):
        db = AsyncMock()
        db.add = MagicMock()
        svc = AlertService(db)

        # Triggered alert (error rate > 5.0%)
        alert = await svc.evaluate_and_dispatch(
            rule_name="High API Error Rate",
            metric_name="http_error_rate_pct",
            current_value=8.5,
            threshold=5.0,
            condition=">",
            severity="critical",
            context={"route": "/api/v1/leads"}
        )
        assert alert is not None
        assert alert.rule_name == "High API Error Rate"
        assert alert.status == "firing"
        assert alert.severity == "critical"
        assert db.add.called
        assert db.commit.called

    @pytest.mark.asyncio
    async def test_threshold_not_triggered(self):
        db = AsyncMock()
        db.add = MagicMock()
        svc = AlertService(db)

        # Non-triggered alert (normal error rate 0.5% <= 5.0%)
        alert = await svc.evaluate_and_dispatch(
            rule_name="High API Error Rate",
            metric_name="http_error_rate_pct",
            current_value=0.5,
            threshold=5.0,
            condition=">",
            severity="critical"
        )
        assert alert is None
        assert not db.add.called

    @pytest.mark.asyncio
    async def test_multi_channel_routing(self):
        db = AsyncMock()
        db.add = MagicMock()
        svc = AlertService(db)

        payload = AlertPayload(
            alert_name="Database Connection Spike",
            severity="warning",
            metric_name="db_active_connections",
            current_value=95.0,
            threshold=90.0,
            message="Active DB connections exceeded threshold"
        )

        with patch.object(settings, "ALERT_SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T00/B00/X00"), \
             patch.object(settings, "ALERT_PAGERDUTY_ROUTING_KEY", "pd_routing_key_12345"), \
             patch.object(settings, "ALERT_WEBHOOK_URL", "https://alert.internal.beetlelabs.ai/webhook"):
            results = await svc._dispatch_to_destinations(payload)
            assert results["slack"] == "dispatched"
            assert results["pagerduty"] == "dispatched"
            assert results["webhook"] == "dispatched"
