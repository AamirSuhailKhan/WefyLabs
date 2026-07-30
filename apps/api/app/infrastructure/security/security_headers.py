from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Enterprise Security Middleware injecting OWASP recommended HTTP Security Headers:
    - HSTS (Strict-Transport-Security)
    - Content-Security-Policy (CSP)
    - X-Frame-Options (Clickjacking defense)
    - X-Content-Type-Options (MIME sniffing defense)
    - Referrer-Policy
    - Permissions-Policy
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Enforce HTTPS HSTS for 1 year
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        # Prevent clickjacking by disallowing iframe embedding
        response.headers["X-Frame-Options"] = "DENY"
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissions Policy
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Content Security Policy
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;"

        return response
