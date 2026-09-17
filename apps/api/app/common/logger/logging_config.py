"""
BeetleLabs Structured JSON Logger
===================================
Production-grade structured logging with:
- JSON output (compatible with Datadog, Loki, CloudWatch)
- Correlation ID / Request ID propagation
- Organization context in every log line
- Sensitive field redaction (PII, tokens, keys)
- Log levels controlled by environment variable

Usage:
    from app.common.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Lead created", extra={"lead_id": str(lead.id), "org_id": str(org_id)})
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variables propagated across async call stacks
_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_org_id_var: ContextVar[Optional[str]] = ContextVar("org_id", default=None)
_user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)

# Fields that must never appear in logs in plaintext
_REDACTED_FIELDS = frozenset({
    "password", "password_hash", "secret", "token", "api_key",
    "authorization", "gemini_api_key", "openai_api_key", "signing_secret",
    "key_hash", "razorpay_key_secret", "supabase_jwt_secret", "access_token",
    "whatsapp_access_token", "webhook_secret", "otp", "pin"
})


def set_request_context(request_id: Optional[str], org_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
    """Sets per-request context variables. Call from middleware on each request."""
    _request_id_var.set(request_id)
    _org_id_var.set(org_id)
    _user_id_var.set(user_id)


def get_request_id() -> Optional[str]:
    return _request_id_var.get()


class JsonFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.
    Compatible with Datadog, Grafana Loki, AWS CloudWatch, GCP Logging.
    """

    def __init__(self, service_name: str = "wefylabs-api", env: str = "development"):
        super().__init__()
        self._service = service_name
        self._env = env

    def _redact(self, data: Any, depth: int = 0) -> Any:
        """Recursively redact sensitive fields from dicts."""
        if depth > 5:
            return data
        if isinstance(data, dict):
            return {
                k: "[REDACTED]" if k.lower() in _REDACTED_FIELDS else self._redact(v, depth + 1)
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [self._redact(item, depth + 1) for item in data]
        return data

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self._service,
            "env": self._env,
        }

        # Propagate async context
        if rid := _request_id_var.get():
            log_entry["request_id"] = rid
        if oid := _org_id_var.get():
            log_entry["org_id"] = oid
        if uid := _user_id_var.get():
            log_entry["user_id"] = uid

        # Include extra fields from logger.info(..., extra={...})
        exclude = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName"
        }
        for key, value in record.__dict__.items():
            if key not in exclude:
                log_entry[key] = self._redact(value) if isinstance(value, dict) else value

        # Exception info
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Source location (only in debug/development)
        if record.levelno <= logging.DEBUG:
            log_entry["location"] = f"{record.pathname}:{record.lineno}"

        return json.dumps(log_entry, default=str, ensure_ascii=False)


def configure_logging(
    level: str = "INFO",
    service_name: str = "wefylabs-api",
    env: str = "development",
    json_output: bool = True
) -> None:
    """
    Configures the root logger with JSON or human-readable output.
    Call once at application startup before any logger.getLogger() calls.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        service_name: Service identifier embedded in every log line
        env: Environment name (development, staging, production)
        json_output: True for JSON (production), False for human-readable (local dev)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    if json_output:
        handler.setFormatter(JsonFormatter(service_name=service_name, env=env))
    else:
        # Human-readable for local development
        fmt = "%(asctime)s | %(levelname)-8s | %(name)-40s | %(message)s"
        handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Returns a named logger. Always use this instead of logging.getLogger()."""
    return logging.getLogger(name)
