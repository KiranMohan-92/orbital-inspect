import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

import main
from auth.jwt_service import create_access_token
from config import settings
from main import app


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
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret-for-auth-e2e")


def _auth_headers(role: str, org_id: str = "org-secure") -> dict[str, str]:
    token = create_access_token(user_id=f"{role}-user", org_id=org_id, role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_analysis_requires_auth_when_enabled(client, auth_mode, sample_image_bytes):
    response = await client.post(
        "/api/analyses",
        files={"image": ("secure.jpg", sample_image_bytes, "image/jpeg")},
        data={"asset_type": "satellite"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_analysis_rejects_viewer_role(client, auth_mode, sample_image_bytes):
    response = await client.post(
        "/api/analyses",
        files={"image": ("secure.jpg", sample_image_bytes, "image/jpeg")},
        data={"asset_type": "satellite"},
        headers=_auth_headers("viewer"),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_analysis_accepts_analyst_role_and_passes_user_context(
    client,
    auth_mode,
    sample_image_bytes,
):
    with patch.object(main, "_create_analysis_record", AsyncMock(return_value="analysis-secure-1")) as create_record:
        response = await client.post(
            "/api/analyses",
            files={"image": ("secure.jpg", sample_image_bytes, "image/jpeg")},
            data={
                "asset_type": "compute_platform",
                "norad_id": "25544",
                "context": "Secure analyst submission",
            },
            headers=_auth_headers("analyst", org_id="org-analyst"),
        )

    assert response.status_code == 200
    assert response.json()["analysis_id"] == "analysis-secure-1"
    assert response.headers["x-request-id"] == response.json()["request_id"]
    called_user = create_record.await_args.kwargs["user"]
    assert called_user.org_id == "org-analyst"
    assert called_user.role == "analyst"
    assert isinstance(create_record.await_args.kwargs["request_id"], str)


@pytest.mark.asyncio
async def test_list_analyses_uses_jwt_org_scope(client, auth_mode):
    mock_session = _MockSessionContext()
    repo = AsyncMock()
    repo.list_analyses = AsyncMock(return_value=([
        SimpleNamespace(
            id="analysis-1",
            status="completed",
            asset_type="satellite",
            norad_id="25544",
            degraded=False,
            failure_reasons=[],
            report_completeness="COMPLETE",
            evidence_completeness_pct=100.0,
            created_at=None,
            completed_at=None,
        )
    ], 1))

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.AnalysisRepository", return_value=repo):
        response = await client.get("/api/analyses", headers=_auth_headers("viewer", org_id="org-alpha"))

    assert response.status_code == 200
    repo.list_analyses.assert_awaited_once_with(org_id="org-alpha", limit=20, offset=0)


@pytest.mark.asyncio
async def test_webhook_list_requires_admin_role_when_auth_enabled(client, auth_mode):
    response = await client.get("/api/webhooks", headers=_auth_headers("analyst"))

    assert response.status_code == 403
