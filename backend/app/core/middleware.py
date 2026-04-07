"""
FastAPI middleware stack.

Middleware order matters — outermost runs first on request, last on response:
1. RequestIDMiddleware   — assigns trace ID to every request
2. LoggingMiddleware     — structured access logs with duration
3. (CORS handled by FastAPI's CORSMiddleware in main.py)
4. (Rate limiting handled per-route via Redis)
"""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Assigns a unique X-Request-ID to every request.
    Binds it to structlog context so all logs in a request carry it.
    Returns it in response headers for client-side correlation.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind to structlog context — available in all downstream log calls
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured access logging: method, path, status, duration.
    Skips health check endpoints to avoid log noise.
    """

    SKIP_PATHS = {"/api/v1/health", "/favicon.ico", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        log = logger.bind(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        if response.status_code >= 500:
            log.error("request.error")
        elif response.status_code >= 400:
            log.warning("request.client_error")
        else:
            log.info("request.complete")

        return response
