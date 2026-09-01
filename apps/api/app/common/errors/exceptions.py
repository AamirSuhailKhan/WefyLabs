"""
BeetleLabs Unified Error Model
===============================
Consistent API error responses. Never leaks stack traces to clients.
Maps internal domain exceptions to appropriate HTTP status codes.

Usage:
    raise LeadNotFoundError(lead_id)
    raise PermissionDeniedError("leads:delete")
    raise ValidationError("budget_min", "Must be greater than 0")
"""
from __future__ import annotations

import logging
import traceback
from typing import Any, Dict, Optional, List
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ─── Error Response Schema ──────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    """Individual field-level error detail."""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ApiErrorResponse(BaseModel):
    """Canonical API error response returned for every error."""
    success: bool = False
    error: str
    error_code: str
    message: str
    details: Optional[List[ErrorDetail]] = None
    request_id: Optional[str] = None


# ─── Domain Exception Hierarchy ─────────────────────────────────────────────

class BeetleLabsError(Exception):
    """Base exception for all BeetleLabs domain errors."""
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(self, message: Optional[str] = None, details: Optional[List[ErrorDetail]] = None):
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)


class NotFoundError(BeetleLabsError):
    """Resource not found."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"
    message = "The requested resource was not found."


class LeadNotFoundError(NotFoundError):
    error_code = "LEAD_NOT_FOUND"
    def __init__(self, lead_id: Any = None):
        super().__init__(message=f"Lead '{lead_id}' not found." if lead_id else "Lead not found.")


class ContactNotFoundError(NotFoundError):
    error_code = "CONTACT_NOT_FOUND"
    def __init__(self, contact_id: Any = None):
        super().__init__(message=f"Contact '{contact_id}' not found." if contact_id else "Contact not found.")


class OrganizationNotFoundError(NotFoundError):
    error_code = "ORGANIZATION_NOT_FOUND"
    def __init__(self, org_id: Any = None):
        super().__init__(message=f"Organization '{org_id}' not found." if org_id else "Organization not found.")


class UserNotFoundError(NotFoundError):
    error_code = "USER_NOT_FOUND"
    def __init__(self, user_id: Any = None):
        super().__init__(message=f"User '{user_id}' not found." if user_id else "User not found.")


class AuthenticationError(BeetleLabsError):
    """Authentication failed — invalid or expired token."""
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTHENTICATION_FAILED"
    message = "Authentication required. Please provide a valid token."


class TokenExpiredError(AuthenticationError):
    error_code = "TOKEN_EXPIRED"
    message = "Your session has expired. Please sign in again."


class PermissionDeniedError(BeetleLabsError):
    """RBAC permission check failed."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "PERMISSION_DENIED"

    def __init__(self, required_permission: Optional[str] = None):
        msg = (
            f"Access denied. Required permission: '{required_permission}'."
            if required_permission
            else "You do not have permission to perform this action."
        )
        super().__init__(message=msg)


class ValidationError(BeetleLabsError):
    """Domain-level validation failure (distinct from HTTP 422)."""
    status_code = 422
    error_code = "VALIDATION_FAILED"

    def __init__(self, field: Optional[str] = None, message: str = "Validation failed."):
        details = [ErrorDetail(field=field, message=message, code="INVALID_VALUE")] if field else None
        super().__init__(message=f"Validation failed: {message}", details=details)


class ConflictError(BeetleLabsError):
    """Resource conflict — duplicate or optimistic lock failure."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"
    message = "A conflict occurred. The resource may have been modified by another request."


class OptimisticLockError(ConflictError):
    """Optimistic lock version mismatch."""
    error_code = "OPTIMISTIC_LOCK_CONFLICT"
    message = "The resource was modified by another request. Please refresh and try again."


class DuplicateError(ConflictError):
    """Duplicate entity detected."""
    error_code = "DUPLICATE_RESOURCE"

    def __init__(self, field: str, value: Any):
        super().__init__(message=f"A resource with {field}='{value}' already exists.")


class TenantIsolationError(BeetleLabsError):
    """Attempt to access data belonging to a different organization."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "TENANT_ISOLATION_VIOLATION"
    message = "Access to this resource is not permitted for your organization."


class QuotaExceededError(BeetleLabsError):
    """Organization has exceeded a plan quota."""
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    error_code = "QUOTA_EXCEEDED"

    def __init__(self, resource: str, limit: int):
        super().__init__(message=f"Plan quota exceeded: {resource} limit is {limit}. Upgrade your plan.")


class RateLimitError(BeetleLabsError):
    """Too many requests."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests. Please slow down and try again."


class IntegrationError(BeetleLabsError):
    """External service integration failed."""
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "INTEGRATION_FAILED"

    def __init__(self, service: str, detail: Optional[str] = None):
        msg = f"Integration with {service} failed."
        if detail:
            msg += f" Detail: {detail}"
        super().__init__(message=msg)


class StorageError(BeetleLabsError):
    """File storage operation failed."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "STORAGE_ERROR"
    message = "File storage operation failed."


# ─── FastAPI Exception Handlers ──────────────────────────────────────────────

def _get_request_id(request: Request) -> Optional[str]:
    return request.headers.get("x-request-id") or request.headers.get("x-correlation-id")


async def beetlelabs_error_handler(request: Request, exc: BeetleLabsError) -> JSONResponse:
    """Handles all domain-specific BeetleLabs errors with consistent response structure."""
    request_id = _get_request_id(request)
    logger.warning(
        f"[{exc.error_code}] {exc.message}",
        extra={"request_id": request_id, "path": request.url.path, "error_code": exc.error_code}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiErrorResponse(
            error=exc.__class__.__name__,
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
            request_id=request_id
        ).model_dump(exclude_none=True)
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles Pydantic validation errors with field-level detail."""
    request_id = _get_request_id(request)
    details = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error.get("loc", []) if loc != "body")
        details.append(ErrorDetail(
            field=field or None,
            message=error.get("msg", "Invalid value"),
            code=error.get("type", "INVALID_VALUE").upper()
        ))
    return JSONResponse(
        status_code=422,
        content=ApiErrorResponse(
            error="RequestValidationError",
            error_code="REQUEST_VALIDATION_FAILED",
            message=f"Request validation failed. {len(details)} field(s) invalid.",
            details=details,
            request_id=request_id
        ).model_dump(exclude_none=True)
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catches all unhandled exceptions.
    Logs full stack trace server-side. Returns generic message to client.
    Never leaks internal error details.
    """
    request_id = _get_request_id(request)
    logger.error(
        f"[UNHANDLED EXCEPTION] {exc.__class__.__name__}: {exc}",
        extra={"request_id": request_id, "path": request.url.path},
        exc_info=True
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ApiErrorResponse(
            error="InternalServerError",
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred. Our team has been notified.",
            request_id=request_id
        ).model_dump(exclude_none=True)
    )


def register_error_handlers(app) -> None:
    """
    Registers all error handlers on the FastAPI app.
    Call this once in app startup, before any routes are mounted.
    """
    from fastapi.exceptions import RequestValidationError
    app.add_exception_handler(BeetleLabsError, beetlelabs_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
