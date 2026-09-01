"""
BeetleLabs Request Correlation Middleware
==========================================
Assigns a unique X-Request-ID to every inbound request.
Propagates it through async context for structured logging and error responses.
Also injects tenant context (organization_id, user_id) for log correlation.
"""
from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.common.logger.logging_config import set_request_context, get_logger

logger = get_logger(__name__)


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Assigns X-Request-ID to every request.
    Returns it in the response header.
    Propagates to async context for log correlation.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = (
            request.headers.get("x-request-id")
            or request.headers.get("x-correlation-id")
            or str(uuid.uuid4())
        )

        # Set correlation context for this async call chain
        set_request_context(request_id=request_id)

        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Attach request ID to response header
        response.headers["x-request-id"] = request_id
        response.headers["x-response-time-ms"] = str(duration_ms)

        # Log every request (access log in structured JSON)
        logger.info(
            f"{request.method} {request.url.path} → {response.status_code}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent", "")[:200],
            }
        )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects production-grade HTTP security headers on every response.
    Hardened against common web vulnerabilities.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        # Remove server fingerprint
        response.headers.pop("server", None)
        return response
