"""
RFC 7807 Problem Details error envelope for FastAPI.

Registers handlers for HTTPException, RequestValidationError, and unhandled
exceptions. All error responses use the application/problem+json content type.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

log = logging.getLogger(__name__)

CONTENT_TYPE = "application/problem+json"

# Map HTTP status codes to relative URI error type slugs.
_STATUS_TYPE: dict[int, str] = {
    400: "/errors/bad-request",
    401: "/errors/unauthorized",
    403: "/errors/forbidden",
    404: "/errors/not-found",
    405: "/errors/method-not-allowed",
    409: "/errors/conflict",
    422: "/errors/validation-error",
    429: "/errors/too-many-requests",
    500: "/errors/internal-error",
    503: "/errors/service-unavailable",
}

_STATUS_TITLE: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    503: "Service Unavailable",
}


def _error_type(status: int) -> str:
    return _STATUS_TYPE.get(status, f"/errors/http-{status}")


def _error_title(status: int) -> str:
    return _STATUS_TITLE.get(status, f"HTTP {status}")


def _trace_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    trace_id: str | None = None

    def response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status,
            content=self.model_dump(exclude_none=False),
            headers={"Content-Type": CONTENT_TYPE},
        )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    status = exc.status_code
    problem = ProblemDetail(
        type=_error_type(status),
        title=_error_title(status),
        status=status,
        detail=str(exc.detail) if exc.detail else _error_title(status),
        instance=str(request.url.path),
        trace_id=_trace_id(request),
    )
    response = problem.response()
    # Preserve any custom headers set on the original HTTPException (e.g.
    # Deprecation, Sunset, Link headers from legacy endpoint wrappers).
    if getattr(exc, "headers", None):
        for key, value in exc.headers.items():
            response.headers[key] = value
    return response


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors: list[dict[str, Any]] = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            }
        )

    detail = "; ".join(
        f"{e['field']}: {e['message']}" if e["field"] else e["message"]
        for e in errors
    )

    problem = ProblemDetail(
        type=_error_type(422),
        title=_error_title(422),
        status=422,
        detail=detail or "Request validation failed",
        instance=str(request.url.path),
        trace_id=_trace_id(request),
    )
    response = problem.response()
    # Attach structured field errors as an extension field.
    body = problem.model_dump(exclude_none=False)
    body["errors"] = errors
    return JSONResponse(
        status_code=422,
        content=body,
        headers={"Content-Type": CONTENT_TYPE},
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    log.error(
        "Unhandled exception: %s %s — %r",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    problem = ProblemDetail(
        type=_error_type(500),
        title=_error_title(500),
        status=500,
        detail="An unexpected error occurred. Please try again or contact support.",
        instance=str(request.url.path),
        trace_id=_trace_id(request),
    )
    return problem.response()


def register_error_handlers(app: FastAPI) -> None:
    """Register all RFC 7807 error handlers on the FastAPI application."""
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
