from typing import Dict, Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse

_idempotency_cache: Dict[str, Tuple[int, bytes, Dict[str, str]]] = {}

class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware checking Idempotency-Key header on state-modifying requests (POST, PATCH, PUT).
    Returns cached response if same idempotency key is re-sent within TTL.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in ("POST", "PATCH", "PUT"):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        cache_key = f"{request.url.path}:{idempotency_key}"
        if cache_key in _idempotency_cache:
            status_code, body, headers = _idempotency_cache[cache_key]
            res = StarletteResponse(content=body, status_code=status_code)
            for k, v in headers.items():
                if k.lower() not in ("content-length", "content-type"):
                    res.headers[k] = v
            res.headers["X-Cache-Lookup"] = "HIT-IDEMPOTENT"
            return res

        response = await call_next(request)

        if response.status_code < 400:
            response_body = [chunk async for chunk in response.body_iterator]
            response.body_iterator = iterate_in_threadpool(iter(response_body))
            full_body = b"".join(response_body)
            _idempotency_cache[cache_key] = (
                response.status_code,
                full_body,
                dict(response.headers)
            )

        return response

async def iterate_in_threadpool(iterator):
    for item in iterator:
        yield item
