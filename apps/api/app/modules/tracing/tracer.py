"""
OpenTelemetry W3C Distributed Tracing Engine
============================================
Provides distributed tracing with W3C traceparent context headers.
Format: 00-{trace_id}-{span_id}-{trace_flags}
"""
import uuid
import time
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

from app.modules.logging.json_logger import get_trace_context, set_trace_context

logger = logging.getLogger(__name__)


def generate_trace_id() -> str:
    """Generates a 32-character hex trace ID."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generates a 16-character hex span ID."""
    return uuid.uuid4().hex[:16]


class Span:
    """Represents a single operation span in a distributed trace."""
    def __init__(self, name: str, parent_span_id: Optional[str] = None):
        self.name = name
        self.trace_id = get_trace_context().get("trace_id") or generate_trace_id()
        self.span_id = generate_span_id()
        self.parent_span_id = parent_span_id
        self.start_time = time.time()
        self.attributes: Dict[str, Any] = {}
        self.status = "OK"
        self.error: Optional[str] = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_error(self, error: Exception) -> None:
        self.status = "ERROR"
        self.error = str(error)

    def finish(self) -> None:
        duration_ms = round((time.time() - self.start_time) * 1000, 2)
        logger.info(
            f"[SPAN] {self.name} | Duration: {duration_ms}ms | Status: {self.status}",
            extra={"extra_payload": {
                "span_name": self.name,
                "span_id": self.span_id,
                "parent_span_id": self.parent_span_id,
                "duration_ms": duration_ms,
                "attributes": self.attributes,
                "status": self.status,
                "error": self.error,
            }}
        )


class Tracer:
    """OpenTelemetry W3C Tracing Interface."""

    @classmethod
    def parse_traceparent(cls, traceparent_header: Optional[str]) -> Dict[str, str]:
        """
        Parses W3C traceparent header:
        00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
        """
        if not traceparent_header:
            return {"trace_id": generate_trace_id(), "parent_span_id": None}

        parts = traceparent_header.split("-")
        if len(parts) >= 3 and parts[0] == "00":
            return {"trace_id": parts[1], "parent_span_id": parts[2]}

        return {"trace_id": generate_trace_id(), "parent_span_id": None}

    @classmethod
    def format_traceparent(cls, trace_id: str, span_id: str) -> str:
        """Formats W3C traceparent header string."""
        return f"00-{trace_id}-{span_id}-01"

    @classmethod
    @contextmanager
    def start_span(cls, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Context manager for tracing code execution blocks."""
        ctx = get_trace_context()
        parent_span_id = ctx.get("span_id")
        span = Span(name=name, parent_span_id=parent_span_id)

        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)

        # Update context for child spans
        set_trace_context(trace_id=span.trace_id, span_id=span.span_id)

        try:
            yield span
        except Exception as exc:
            span.set_error(exc)
            raise
        finally:
            span.finish()
            # Restore parent span ID
            set_trace_context(span_id=parent_span_id)
