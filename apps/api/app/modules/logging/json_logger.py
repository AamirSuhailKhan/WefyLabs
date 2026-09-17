"""
Structured JSON Logger
======================
Enterprise Production Logger outputting single-line JSON logs with
ContextVar-based request context propagation.

Never use print() or plain string formatters in production.
"""
import sys
import json
import logging
import time
from datetime import datetime, timezone
from contextvars import ContextVar
from typing import Optional, Dict, Any

# Context Variables for Request Propagation
trace_context_var: ContextVar[Dict[str, Any]] = ContextVar(
    "trace_context_var",
    default={
        "request_id": None,
        "correlation_id": None,
        "trace_id": None,
        "span_id": None,
        "organization_id": None,
        "workspace_id": None,
        "user_id": None,
        "service": "wefylabs-api",
        "module": "core",
    }
)


def set_trace_context(
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    service: str = "wefylabs-api",
    module: str = "core",
) -> None:
    """Sets current thread/async task trace context."""
    current = trace_context_var.get().copy()
    if request_id: current["request_id"] = request_id
    if correlation_id: current["correlation_id"] = correlation_id
    if trace_id: current["trace_id"] = trace_id
    if span_id: current["span_id"] = span_id
    if organization_id: current["organization_id"] = organization_id
    if workspace_id: current["workspace_id"] = workspace_id
    if user_id: current["user_id"] = user_id
    if service: current["service"] = service
    if module: current["module"] = module
    trace_context_var.set(current)


def get_trace_context() -> Dict[str, Any]:
    """Retrieves current thread/async task trace context."""
    return trace_context_var.get()


class JSONFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON strings."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = get_trace_context()
        log_object = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "service": ctx.get("service", "wefylabs-api"),
            "module": ctx.get("module", record.module),
            "environment": "production",
            "request_id": ctx.get("request_id"),
            "correlation_id": ctx.get("correlation_id"),
            "trace_id": ctx.get("trace_id"),
            "span_id": ctx.get("span_id"),
            "organization_id": ctx.get("organization_id"),
            "user_id": ctx.get("user_id"),
        }

        # Include exception details if present
        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)

        # Include extra payload if present
        if hasattr(record, "extra_payload") and isinstance(record.extra_payload, dict):
            log_object["extra"] = record.extra_payload

        try:
            return json.dumps(log_object, default=str)
        except Exception as exc:
            return json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "message": f"Log serialization failure: {exc}",
                "original_message": str(record.msg),
            })


def configure_structured_logging(level: int = logging.INFO) -> None:
    """Configures global Python root logger with JSONFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(stream_handler)
