import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

import main
from config import settings
from main import app
from services.metrics_service import record_analysis_created, record_request, reset_metrics
from services.observability_service import setup_observability
from services.readiness_service import readiness_snapshot


def test_setup_observability_is_safe_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "OTEL_ENABLED", False)
    monkeypatch.setattr(settings, "OTEL_REQUIRED", False)

    state = setup_observability(service_version="test")

    assert state["enabled"] is False
    assert state["instrumented"] is False
    assert state["exporter"] == "disabled"
    assert state["endpoint"] is None


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def observability_auth_mode(monkeypatch):
    reset_metrics()
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret-for-observability")
    monkeypatch.setattr(settings, "PROMETHEUS_METRICS_ENABLED", True)
    monkeypatch.setattr(settings, "OBSERVABILITY_SHARED_TOKEN", "observability-token")
    monkeypatch.setattr(settings, "OBSERVABILITY_PREVIOUS_TOKENS", ["observability-token-previous"])


@pytest.mark.asyncio
async def test_readiness_snapshot_requires_observability_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "OTEL_REQUIRED", True)
    monkeypatch.setattr(settings, "REDIS_REQUIRED", False)

    with patch("services.readiness_service.check_database_health", AsyncMock(return_value={"ok": True})), \
         patch("services.readiness_service.check_redis_health", AsyncMock(return_value={"ok": True})), \
         patch("services.readiness_service.check_storage_health", AsyncMock(return_value={"ok": True})), \
         patch("services.readiness_service.should_use_queue_dispatch", return_value=False), \
         patch("services.readiness_service.telemetry_state", return_value={
             "enabled": True,
             "instrumented": False,
             "exporter": "unavailable",
             "error": "collector unavailable",
         }):
        snapshot = await readiness_snapshot()

    assert snapshot["observability_required"] is True
    assert snapshot["observability"]["instrumented"] is False
    assert snapshot["ok"] is False


@pytest.mark.asyncio
async def test_observability_token_can_access_metrics_endpoint(client, observability_auth_mode, monkeypatch):
    monkeypatch.setattr(main, "telemetry_state", lambda: {
        "enabled": True,
        "instrumented": True,
        "service_name": "orbital-inspect-api",
        "exporter": "otlp_http",
        "endpoint": "http://collector:4318/v1/traces",
    })
    record_request("GET", "/api/health", 200, 5.2)
    record_analysis_created("satellite")

    response = await client.get(
        "/api/metrics/prometheus",
        headers={"Authorization": "Bearer observability-token"},
    )

    assert response.status_code == 200
    text = response.text
    assert 'orbital_request_latency_avg_ms{method="GET",path="/api/health"} 5.2' in text
    assert 'orbital_analysis_created_total{asset_type="satellite"} 1' in text
    assert 'orbital_observability_exporter_info{service="orbital-inspect-api",exporter="otlp_http"} 1' in text


@pytest.mark.asyncio
async def test_previous_observability_token_is_accepted(client, observability_auth_mode):
    response = await client.get(
        "/api/metrics/prometheus",
        headers={"X-Observability-Token": "observability-token-previous"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_observability_endpoints_require_machine_token_or_admin(client, observability_auth_mode):
    response = await client.get("/api/metrics/prometheus")

    assert response.status_code == 401
