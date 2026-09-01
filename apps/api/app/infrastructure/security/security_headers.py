from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Enterprise Security Middleware injecting OWASP recommended HTTP Security Headers.

    HSTS is only set when the connection is actually over HTTPS (detected via the
    X-Forwarded-Proto header from Cloudflare / load balancer, or direct TLS).
    This prevents the browser from permanently redirecting to HTTPS before TLS
    is actually provisioned — a critical misconfiguration in pre-production environments.

    Headers set:
    - HSTS (Strict-Transport-Security)   — HTTPS only
    - Content-Security-Policy (CSP)
    - X-Frame-Options                    — Clickjacking defense
    - X-Content-Type-Options             — MIME sniffing defense
    - Referrer-Policy
    - Permissions-Policy
    - X-Request-ID                       — Correlation tracing
    """

    _IS_PROD = settings.ENV.lower() in ("production", "prod", "staging")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # ── HSTS: only inject when the connection is genuinely HTTPS ──────────
        # Cloudflare / ALB / nginx forward the original scheme via X-Forwarded-Proto.
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        is_https = forwarded_proto.lower() == "https" or request.url.scheme == "https"
        if is_https:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # ── Anti-clickjacking ─────────────────────────────────────────────────
        response.headers["X-Frame-Options"] = "DENY"

        # ── MIME sniffing defense ─────────────────────────────────────────────
        response.headers["X-Content-Type-Options"] = "nosniff"

        # ── Referrer Policy ───────────────────────────────────────────────────
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # ── Permissions Policy ────────────────────────────────────────────────
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )

        # ── Content Security Policy ───────────────────────────────────────────
        # Google OAuth requires accounts.google.com in connect-src and frame-src.
        # Google Fonts requires fonts.googleapis.com and fonts.gstatic.com.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://accounts.google.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://accounts.google.com; "
            "frame-src 'self' https://accounts.google.com; "
            "object-src 'none'; "
            "base-uri 'self';"
        )

        # ── Remove server fingerprinting ──────────────────────────────────────
        for _hdr in ("server", "x-powered-by"):
            try:
                del response.headers[_hdr]
            except (KeyError, AttributeError):
                pass

        return response
