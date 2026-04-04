"""
FastAPI middleware for structured request/response logging.
"""

import time
import uuid

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import settings
from services.metrics_service import record_request, record_rate_limit
from services.observability_service import current_trace_id


log = structlog.get_logger("middleware.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            trace_id=current_trace_id(),
        )
        response: Response | None = None

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            status_code = 500

            if settings.METRICS_ENABLED:
                record_request(request.method, request.url.path, status_code, duration_ms)

            log.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=status_code,
                duration_ms=duration_ms,
                client=request.client.host if request.client else "unknown",
                request_id=request_id,
            )
            clear_contextvars()
            raise

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        status_code = response.status_code

        if settings.METRICS_ENABLED:
            record_request(request.method, request.url.path, status_code, duration_ms)

        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=status_code,
            duration_ms=duration_ms,
            client=request.client.host if request.client else "unknown",
            request_id=request_id,
        )
        clear_contextvars()

        response.headers["X-Request-ID"] = request_id
        trace_id = current_trace_id()
        if trace_id:
            response.headers["X-Trace-ID"] = trace_id
        rate_limit = getattr(request.state, "rate_limit", None)
        if rate_limit:
            response.headers["X-RateLimit-Limit"] = str(rate_limit["limit"])
            response.headers["X-RateLimit-Remaining"] = str(rate_limit["remaining"])
            response.headers["X-RateLimit-Reset"] = str(rate_limit["reset_seconds"])
            if response.status_code == 429:
                record_rate_limit(request.url.path)
        return response
