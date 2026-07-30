from datetime import datetime, timezone
from fastapi import Request, FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.infrastructure.errors.exceptions import BaseAPIException

def register_exception_handlers(app: FastAPI) -> None:
    """Registers unified JSON error response handlers for FastAPI application."""

    @app.exception_handler(BaseAPIException)
    async def base_api_exception_handler(request: Request, exc: BaseAPIException):
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": request_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": str(request.url.path)
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request body or parameter validation failed",
                    "details": {"errors": exc.errors()},
                    "request_id": request_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": str(request.url.path)
                }
            }
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        request_id = getattr(request.state, "request_id", "unknown")
        code = "HTTP_ERROR"
        if exc.status_code == 401: code = "UNAUTHORIZED"
        elif exc.status_code == 403: code = "FORBIDDEN"
        elif exc.status_code == 404: code = "NOT_FOUND"
        elif exc.status_code == 429: code = "RATE_LIMIT_EXCEEDED"

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": str(exc.detail),
                    "request_id": request_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": str(request.url.path)
                }
            }
        )
