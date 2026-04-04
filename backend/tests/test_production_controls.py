import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

import main
from auth.jwt_service import create_access_token
from config import Settings, settings
from main import app
from services.metrics_service import (
    record_analysis_created,
    record_analysis_terminal,
    record_artifact_generated,
    record_dead_letter,
    record_rate_limit,
    record_request,
    record_retry,
    reset_metrics,
)
from services.storage_service import StoredObject


class _MockSessionContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_mode(monkeypatch):
    reset_metrics()
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret-for-production-controls")
    monkeypatch.setattr(settings, "PROMETHEUS_METRICS_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "memory")


def _auth_headers(role: str, org_id: str = "org-secure", extra_claims: dict | None = None) -> dict[str, str]:
    token = create_access_token(
        user_id=f"{role}-user",
        org_id=org_id,
        role=role,
        extra_claims=extra_claims,
    )
    return {"Authorization": f"Bearer {token}"}


def test_settings_reject_demo_mode_in_production():
    with pytest.raises(ValueError, match="DEMO_MODE must be false"):
        Settings(
            GEMINI_API_KEY="test-key",
            APP_ENV="production",
            DEMO_MODE=True,
            AUTH_ENABLED=True,
            JWT_SECRET="production-secret",
        )


def test_settings_require_auth_in_staging():
    with pytest.raises(ValueError, match="AUTH_ENABLED must be true"):
        Settings(
            GEMINI_API_KEY="test-key",
            APP_ENV="staging",
            DEMO_MODE=False,
            AUTH_ENABLED=False,
        )


@pytest.mark.asyncio
async def test_ready_endpoint_returns_snapshot_for_admin(client, auth_mode):
    expected = {
        "ok": True,
        "database": {"ok": True},
        "queue": {"ok": True},
        "storage": {"ok": True},
        "queue_required": True,
    }
    with patch.object(main, "readiness_snapshot", AsyncMock(return_value=expected)):
        response = await client.get("/api/ready", headers=_auth_headers("admin"))

    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.asyncio
async def test_ready_endpoint_accepts_observability_token(client, auth_mode, monkeypatch):
    monkeypatch.setattr(settings, "OBSERVABILITY_SHARED_TOKEN", "ops-token")
    expected = {
        "ok": True,
        "database": {"ok": True},
        "queue": {"ok": True},
        "storage": {"ok": True},
        "queue_required": False,
        "observability_required": False,
    }
    with patch.object(main, "readiness_snapshot", AsyncMock(return_value=expected)):
        response = await client.get("/api/ready", headers={"Authorization": "Bearer ops-token"})

    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.asyncio
async def test_prometheus_metrics_renders_production_counters(client, auth_mode):
    record_request("POST", "/api/analyses", 202, 12.5)
    record_request("GET", "/api/health", 200, 4.0)
    record_analysis_created("satellite")
    record_analysis_terminal("completed_partial")
    record_retry("scheduled")
    record_dead_letter("analysis_job_failed")
    record_artifact_generated("pdf")
    record_rate_limit("/api/reports/inline/generate-pdf")

    response = await client.get("/api/metrics/prometheus", headers=_auth_headers("admin"))

    assert response.status_code == 200
    text = response.text
    assert 'orbital_requests_total{key="POST|/api/analyses|202"} 1' in text
    assert 'orbital_request_latency_avg_ms{method="GET",path="/api/health"} 4.0' in text
    assert 'orbital_analysis_created_total{asset_type="satellite"} 1' in text
    assert 'orbital_analysis_terminal_total{status="completed_partial"} 1' in text
    assert 'orbital_analysis_retries_total{status="scheduled"} 1' in text
    assert 'orbital_analysis_dead_letters_total{reason="analysis_job_failed"} 1' in text
    assert 'orbital_report_artifacts_total{kind="pdf"} 1' in text
    assert 'orbital_rate_limit_hits_total{bucket="/api/reports/inline/generate-pdf"} 1' in text


@pytest.mark.asyncio
async def test_dead_letters_endpoint_uses_org_scope(client, auth_mode):
    mock_session = _MockSessionContext()
    repo = AsyncMock()
    repo.list_dead_letters = AsyncMock(return_value=[
        SimpleNamespace(
            id="dead-1",
            analysis_id="analysis-1",
            job_id="analysis:analysis-1",
            queue_name="arq:queue",
            attempts=3,
            error_message="queue timeout",
            created_at=None,
        )
    ])

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.AnalysisRepository", return_value=repo):
        response = await client.get("/api/ops/dead-letters", headers=_auth_headers("admin", org_id="org-alpha"))

    assert response.status_code == 200
    repo.list_dead_letters.assert_awaited_once_with(org_id="org-alpha", limit=50)
    assert response.json()["items"][0]["analysis_id"] == "analysis-1"


@pytest.mark.asyncio
async def test_rotate_api_key_updates_org_and_returns_plaintext_key(client, auth_mode):
    mock_session = _MockSessionContext()
    org_repo = AsyncMock()
    org_repo.get = AsyncMock(return_value=SimpleNamespace(id="org-admin", tier="enterprise"))
    org_repo.update_api_key_hash = AsyncMock()
    audit_logs = AsyncMock()

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.OrganizationRepository", return_value=org_repo), \
         patch("db.repository.AuditLogRepository", return_value=audit_logs):
        response = await client.post("/api/admin/api-key/rotate", headers=_auth_headers("admin", org_id="org-admin"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["org_id"] == "org-admin"
    assert payload["api_key"].startswith(f"{settings.API_KEY_PREFIX}_org-admin_")
    org_repo.update_api_key_hash.assert_awaited_once()
    audit_logs.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_audit_logs_returns_org_scoped_entries(client, auth_mode):
    mock_session = _MockSessionContext()
    repo = AsyncMock()
    repo.list_for_org = AsyncMock(return_value=[
        SimpleNamespace(
            id="audit-1",
            action="analysis.created",
            resource_type="analysis",
            resource_id="analysis-1",
            actor_id="admin-user",
            metadata_json={"dispatch_mode": "arq"},
            created_at=None,
        )
    ])

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.AuditLogRepository", return_value=repo):
        response = await client.get("/api/admin/audit", headers=_auth_headers("admin", org_id="org-gamma"))

    assert response.status_code == 200
    repo.list_for_org.assert_awaited_once_with("org-gamma", limit=100)
    assert response.json()["items"][0]["action"] == "analysis.created"


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_headers_and_429(client, auth_mode):
    with patch("auth.dependencies.check_rate_limit", AsyncMock(return_value=(False, {
        "limit": 3,
        "remaining": 0,
        "reset_seconds": 120,
    }))):
        response = await client.post(
            "/api/reports/inline/generate-pdf",
            headers=_auth_headers("analyst"),
            json={"summary": "blocked"},
        )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "120"
    assert response.headers["x-ratelimit-limit"] == "3"
    assert response.headers["x-ratelimit-remaining"] == "0"
    assert response.headers["x-ratelimit-reset"] == "120"


@pytest.mark.asyncio
async def test_report_artifact_generation_returns_signed_download_and_bytes(client, auth_mode):
    mock_session = _MockSessionContext()
    analysis_repo = AsyncMock()
    analysis_repo.get = AsyncMock(return_value=SimpleNamespace(
        id="analysis-1",
        org_id="org-artifacts",
        status="completed",
        classification_result={"valid": True},
        vision_result={"damages": []},
        environment_result={"stressors": []},
        failure_mode_result={"failure_mode": "none"},
        insurance_risk_result={"summary": "Nominal"},
        evidence_gaps=[],
        report_completeness="COMPLETE",
        governance_policy_version="2026-04-03",
        model_manifest={"gemini_model": "gemini-2.5-flash"},
        human_review_required=True,
        decision_blocked_reason=None,
    ))
    report_repo = AsyncMock()
    report_repo.get_by_analysis = AsyncMock(return_value=None)
    report_repo.create = AsyncMock(return_value=SimpleNamespace(id="report-1", version=1))
    report_repo.attach_artifact = AsyncMock()
    audit_logs = AsyncMock()

    artifact_bytes = b"%PDF-1.7 production report"
    stored = StoredObject(
        uri="file:///tmp/report-1.pdf",
        key="reports/report-1-v1.pdf",
        size_bytes=len(artifact_bytes),
        content_type="application/pdf",
        checksum_sha256="abc123",
        local_path="/tmp/report-1.pdf",
    )
    storage = SimpleNamespace(
        store_bytes=lambda **kwargs: stored,
        read_bytes=lambda uri: artifact_bytes,
    )

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
         patch("db.repository.ReportRepository", return_value=report_repo), \
         patch("db.repository.AuditLogRepository", return_value=audit_logs), \
         patch("services.pdf_report_service.generate_html_report", return_value="<html>ok</html>"), \
         patch("services.pdf_report_service.generate_pdf_report", return_value=artifact_bytes), \
         patch("services.storage_service.get_storage_backend", return_value=storage):
        generate = await client.post(
            "/api/reports/analysis-1/generate-pdf",
            headers=_auth_headers("analyst", org_id="org-artifacts"),
        )

        assert generate.status_code == 200
        payload = generate.json()
        assert payload["artifact_kind"] == "pdf"
        assert payload["artifact_download_url"].startswith("/api/reports/artifacts/")
        report_repo.attach_artifact.assert_awaited_once()

        download = await client.get(payload["artifact_download_url"])

    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/pdf")
    assert download.content == artifact_bytes
