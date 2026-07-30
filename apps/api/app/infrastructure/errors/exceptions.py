from typing import Optional, Dict, Any

class BaseAPIException(Exception):
    """Base Exception for all Application & Infrastructure Errors."""
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

class NotFoundException(BaseAPIException):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code=code, status_code=404, details=details)

class BadRequestException(BaseAPIException):
    def __init__(self, message: str = "Bad request", code: str = "BAD_REQUEST", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code=code, status_code=400, details=details)

class UnauthorizedException(BaseAPIException):
    def __init__(self, message: str = "Unauthorized", code: str = "UNAUTHORIZED", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code=code, status_code=401, details=details)

class ForbiddenException(BaseAPIException):
    def __init__(self, message: str = "Forbidden", code: str = "FORBIDDEN", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code=code, status_code=403, details=details)

class ConflictException(BaseAPIException):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code=code, status_code=409, details=details)

class RateLimitException(BaseAPIException):
    def __init__(self, message: str = "Rate limit exceeded", code: str = "RATE_LIMIT_EXCEEDED", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code=code, status_code=429, details=details)
