"""
Calendar Domain Exceptions
==========================
Defines controlled, domain-specific calendar exceptions.
Prevents leaking raw third-party API errors and ensures clear contract boundaries.
"""

class CalendarError(Exception):
    """Base calendar domain error."""
    pass


class CalendarNotConnected(CalendarError):
    """Raised when broker has not connected an external calendar account."""
    pass


class CalendarAuthorizationExpired(CalendarError):
    """Raised when OAuth token has expired and refresh token is invalid or revoked."""
    pass


class CalendarPermissionDenied(CalendarError):
    """Raised when calendar permissions are insufficient (HTTP 403)."""
    pass


class CalendarEventNotFound(CalendarError):
    """Raised when the specified external event is not found (HTTP 404)."""
    pass


class CalendarRateLimited(CalendarError):
    """Raised when calendar provider rate limits requests (HTTP 429)."""
    pass


class CalendarProviderUnavailable(CalendarError):
    """Raised when external calendar provider is temporarily down (HTTP 5xx)."""
    pass


class CalendarAPIError(CalendarError):
    """General external calendar API error."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code
