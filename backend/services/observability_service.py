"""
Optional OpenTelemetry wiring with graceful fallback.

The app can run without OTel packages or collector configuration. When enabled,
this service instruments FastAPI, HTTPX, and SQLAlchemy and exposes current
telemetry state for health/readiness surfaces.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from copy import deepcopy

from config import settings

log = logging.getLogger(__name__)

_telemetry_state: dict[str, object] = {
    "enabled": False,
    "required": False,
    "instrumented": False,
    "service_name": settings.OTEL_SERVICE_NAME,
    "exporter": "disabled",
    "endpoint": None,
    "trace_id": None,
    "error": None,
}
_telemetry_provider = None


def _parse_headers(raw: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for part in [item.strip() for item in raw.split(",") if item.strip()]:
        key, sep, value = part.partition("=")
        if sep and key.strip():
            headers[key.strip()] = value.strip()
    return headers


def _resource_attributes(service_version: str) -> dict[str, str]:
    attrs = {
        "service.name": settings.OTEL_SERVICE_NAME,
        "service.version": service_version,
        "deployment.environment": settings.APP_ENV,
    }
    for part in [item.strip() for item in settings.OTEL_RESOURCE_ATTRIBUTES.split(",") if item.strip()]:
        key, sep, value = part.partition("=")
        if sep and key.strip():
            attrs[key.strip()] = value.strip()
    return attrs


def setup_observability(*, app=None, service_version: str = "0.0.0") -> dict[str, object]:
    global _telemetry_provider

    if _telemetry_state["instrumented"]:
        return telemetry_state()

    if not settings.OTEL_ENABLED:
        _telemetry_state.update(
            {
                "enabled": False,
                "required": settings.OTEL_REQUIRED,
                "instrumented": False,
                "service_name": settings.OTEL_SERVICE_NAME,
                "exporter": "disabled",
                "endpoint": None,
                "error": None,
            }
        )
        return telemetry_state()

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        from db.base import engine

        provider = TracerProvider(
            resource=Resource.create(_resource_attributes(service_version)),
            sampler=TraceIdRatioBased(settings.OTEL_TRACES_SAMPLER_RATIO),
        )
        exporter_kind = "none"

        if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(
                        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                        headers=_parse_headers(settings.OTEL_EXPORTER_OTLP_HEADERS),
                    )
                )
            )
            exporter_kind = "otlp_http"

        if settings.OTEL_CONSOLE_EXPORTER:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            exporter_kind = "console" if exporter_kind == "none" else f"{exporter_kind}+console"

        trace.set_tracer_provider(provider)
        _telemetry_provider = provider

        if app is not None:
            FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        SQLAlchemyInstrumentor().instrument(
            engine=engine.sync_engine,
            tracer_provider=provider,
        )

        _telemetry_state.update(
            {
                "enabled": True,
                "required": settings.OTEL_REQUIRED,
                "instrumented": True,
                "service_name": settings.OTEL_SERVICE_NAME,
                "exporter": exporter_kind,
                "endpoint": settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                "error": None,
            }
        )
    except Exception as exc:
        _telemetry_state.update(
            {
                "enabled": True,
                "required": settings.OTEL_REQUIRED,
                "instrumented": False,
                "service_name": settings.OTEL_SERVICE_NAME,
                "exporter": "unavailable",
                "endpoint": settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                "error": str(exc),
            }
        )
        log.warning("OpenTelemetry setup unavailable", extra={"error": str(exc)})

    return telemetry_state()


def shutdown_observability() -> None:
    global _telemetry_provider
    provider = _telemetry_provider
    _telemetry_provider = None
    if provider is None:
        return
    try:
        provider.shutdown()
    except Exception as exc:
        log.warning("OpenTelemetry shutdown failed", extra={"error": str(exc)})


def current_trace_id() -> str | None:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        context = span.get_span_context()
        if not getattr(context, "is_valid", False):
            return None
        return f"{context.trace_id:032x}"
    except Exception:
        return None


@contextmanager
def start_span(name: str, attributes: dict[str, object] | None = None):
    """
    Start a best-effort span without making telemetry a hard runtime dependency.
    """
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer(settings.OTEL_SERVICE_NAME)
        with tracer.start_as_current_span(name) as span:
            for key, value in (attributes or {}).items():
                if value is None:
                    continue
                span.set_attribute(key, value if isinstance(value, (bool, int, float, str)) else str(value))
            yield span
    except Exception:
        yield None


def telemetry_state() -> dict[str, object]:
    state = deepcopy(_telemetry_state)
    state["trace_id"] = current_trace_id()
    return state
