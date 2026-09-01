import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

# Basic in-memory Prometheus-compatible metrics registry
class MetricsRegistry:
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.total_latency_ms = 0.0

    def record_request(self, status_code: int, latency_ms: float):
        self.request_count += 1
        self.total_latency_ms += latency_ms
        if status_code >= 400:
            self.error_count += 1

    def generate_prometheus_text(self) -> str:
        avg_latency = (self.total_latency_ms / self.request_count) if self.request_count > 0 else 0.0
        return (
            f"# HELP http_requests_total Total number of HTTP requests\n"
            f"# TYPE http_requests_total counter\n"
            f"http_requests_total {self.request_count}\n\n"
            f"# HELP http_errors_total Total number of HTTP error responses (>=400)\n"
            f"# TYPE http_errors_total counter\n"
            f"http_errors_total {self.error_count}\n\n"
            f"# HELP http_request_duration_avg_ms Average HTTP request duration in ms\n"
            f"# TYPE http_request_duration_avg_ms gauge\n"
            f"http_request_duration_avg_ms {avg_latency:.2f}\n"
        )

metrics_registry = MetricsRegistry()

class ObservabilityTracingMiddleware(BaseHTTPMiddleware):
    """
    Production W3C Request Tracing Middleware injecting X-Request-ID and X-Trace-ID,
    measuring latency telemetry, and generating Prometheus metrics.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        trace_id = request.headers.get("X-Trace-ID") or f"trc-{uuid.uuid4().hex[:16]}"

        request.state.request_id = request_id
        request.state.trace_id = trace_id

        response = await call_next(request)

        latency_ms = round((time.time() - start_time) * 1000, 2)
        metrics_registry.record_request(response.status_code, latency_ms)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Server-Latency-ms"] = str(latency_ms)

        logger.info(
            f"[HTTP TRACE] {request.method} {request.url.path} | Status: {response.status_code} | "
            f"Latency: {latency_ms}ms | ReqID: {request_id}"
        )

        return response
