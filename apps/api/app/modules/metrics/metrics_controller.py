from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.modules.metrics.prometheus_collector import metrics

router = APIRouter(tags=["Prometheus Metrics"])


@router.get("/v1/metrics", response_class=PlainTextResponse)
async def export_prometheus_metrics():
    """Exports metrics in standard Prometheus exposition format."""
    return PlainTextResponse(content=metrics.export_prometheus_text(), media_type="text/plain")
