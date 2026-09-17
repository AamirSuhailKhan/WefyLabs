"""
Observability Middleware
========================
Global FastAPI Middleware injecting W3C Trace context, binding structured JSON logger,
and exporting Prometheus metrics on every incoming HTTP request.
"""
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from app.modules.logging.json_logger import set_trace_context, get_trace_context
from app.modules.tracing.tracer import Tracer, generate_trace_id, generate_span_id
from app.modules.metrics.prometheus_collector import metrics

logger = logging.getLogger(__name__)


class EnterpriseObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Production Observability Middleware:
    1. Extracts/Injects X-Request-ID, X-Correlation-ID, W3C traceparent header.
    2. Binds context variables for structured JSON logging.
    3. Records latency and metrics in Prometheus collector.
    4. Attaches correlation headers to HTTP response.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        correlation_id = request.headers.get("X-Correlation-ID") or f"corr-{uuid.uuid4().hex[:12]}"

        # W3C Trace Context
        traceparent = request.headers.get("traceparent")
        parsed_trace = Tracer.parse_traceparent(traceparent)
        trace_id = parsed_trace["trace_id"]
        span_id = generate_span_id()

        # Context Variable binding
        set_trace_context(
            request_id=request_id,
            correlation_id=correlation_id,
            trace_id=trace_id,
            span_id=span_id,
            service="wefylabs-api",
            module="http",
        )

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.trace_id = trace_id

        # Execute downstream handlers
        try:
            response = await call_next(request)
        except Exception as exc:
            duration = time.time() - start_time
            metrics.record_http_request(request.method, request.url.path, 500, duration)
            logger.error(
                f"[HTTP UNHANDLED EXCEPTION] {request.method} {request.url.path} - {exc}",
                exc_info=exc,
            )
            raise

        duration_seconds = time.time() - start_time
        latency_ms = round(duration_seconds * 1000, 2)

        # Record Prometheus metric
        metrics.record_http_request(
            request.method, request.url.path, response.status_code, duration_seconds
        )

        # Inject Response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["traceparent"] = Tracer.format_traceparent(trace_id, span_id)
        response.headers["X-Server-Latency-ms"] = str(latency_ms)

        logger.info(
            f"[HTTP RESPONSE] {request.method} {request.url.path} | Status: {response.status_code} | "
            f"Latency: {latency_ms}ms"
        )

        return response
