"""Core middleware — request ID, request logging, and Prometheus instrumentation."""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger
from app.core.telemetry import REQUEST_COUNT, REQUEST_LATENCY

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate or propagate an X-Request-ID header, and bind it to structlog."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind to structlog context so every log in this request includes it.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Store on request state for downstream access.
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status, and duration for every HTTP request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        # Skip noisy health/metrics endpoints.
        path = request.url.path
        if path not in ("/health", "/metrics"):
            logger.info(
                "http_request",
                method=request.method,
                path=path,
                status=response.status_code,
                duration_ms=duration_ms,
                client=request.client.host if request.client else None,
            )

        return response


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Increment HTTP request counters and observe latency histograms."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        path = request.url.path
        method = request.method
        status = str(response.status_code)

        REQUEST_COUNT.labels(method=method, endpoint=path, status=status).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=path).observe(duration)

        return response
