from fastapi import APIRouter, Depends
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response

router = APIRouter(prefix="/v1/telemetry", tags=["Grafana Telemetry Generator"])


@router.get("/grafana-dashboard", response_model=APIResponse)
async def generate_grafana_dashboard_json(current_broker=Depends(get_current_broker)):
    """Generates standard Grafana Dashboard JSON for system monitoring."""
    dashboard = {
        "title": "BeetleLabs Enterprise Production Telemetry",
        "tags": ["production", "beetlelabs", "sre"],
        "timezone": "browser",
        "schemaVersion": 36,
        "panels": [
            {
                "id": 1,
                "title": "HTTP Requests Rate (req/sec)",
                "type": "timeseries",
                "targets": [{"expr": 'sum(rate(http_requests_total[5m]))', "legendFormat": "Total Requests"}]
            },
            {
                "id": 2,
                "title": "HTTP P95 Latency (seconds)",
                "type": "timeseries",
                "targets": [{"expr": "http_request_duration_avg_seconds", "legendFormat": "Average Latency"}]
            },
            {
                "id": 3,
                "title": "Database Query Count",
                "type": "stat",
                "targets": [{"expr": "db_queries_total", "legendFormat": "Queries"}]
            },
            {
                "id": 4,
                "title": "AI Token Spend per Org (USD)",
                "type": "barplot",
                "targets": [{"expr": "ai_cost_usd_total", "legendFormat": "{{organization_id}}"}]
            }
        ]
    }
    return create_success_response(data=dashboard)
