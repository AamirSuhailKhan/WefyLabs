import uuid
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Middleware attaching X-Request-ID correlation IDs and response execution time header."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.time()

        response = await call_next(request)

        process_time_ms = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(process_time_ms)
        return response
