from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

from auth.dependencies import CurrentUser, get_current_user
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


def _analysis():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id="analysis-1",
        org_id="org-1",
        asset_id="asset-1",
        status="completed",
        asset_type="satellite",
        decision_status="pending_human_review",
        decision_summary={
            "recommended_action": "continue_operations",
            "decision_confidence": "high",
            "decision_rationale": "Low composite with sufficient evidence.",
            "required_human_review": True,
            "blocked": False,
            "blocked_reason": None,
            "evidence_completeness_bucket": "sufficient",
            "urgency": "routine",
            "policy_version": "2026-04-03",
        },
        recurrence_count=1,
        insurance_risk_result={
            "risk_matrix": {"composite": 16},
            "risk_tier": "LOW",
            "underwriting_recommendation": "INSURABLE_STANDARD",
        },
        environment_result={},
        evidence_completeness_pct=100.0,
        degraded=False,
        failure_reasons=[],
        report_completeness="COMPLETE",
        created_at=now,
        completed_at=now,
    )


@pytest.mark.asyncio
async def test_decision_review_approve_updates_status_and_summary(client):
    mock_session = _MockSessionContext()
    analysis_repo = AsyncMock()
    analysis_repo.get = AsyncMock(return_value=_analysis())
    analysis_repo.update_decision_state = AsyncMock()
    audit_logs = AsyncMock()

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
         patch("db.repository.AuditLogRepository", return_value=audit_logs), \
         patch("services.webhook_service.dispatch_registered_webhooks", AsyncMock()):
        response = await client.post(
            "/api/analyses/analysis-1/decision/review",
            json={"action": "approve", "comments": "Approved for ops"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision_status"] == "approved_for_use"
    assert payload["decision_summary"]["recommended_action"] == "continue_operations"
    analysis_repo.update_decision_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_decision_review_override_requires_reason_code_and_updates_summary(client):
    mock_session = _MockSessionContext()
    analysis = _analysis()
    analysis_repo = AsyncMock()
    analysis_repo.get = AsyncMock(return_value=analysis)
    analysis_repo.update_decision_state = AsyncMock()
    audit_logs = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="admin-1",
        org_id="org-1",
        role="admin",
    )
    try:
        with patch("db.base.async_session_factory", return_value=mock_session), \
             patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
             patch("db.repository.AuditLogRepository", return_value=audit_logs), \
             patch("services.webhook_service.dispatch_registered_webhooks", AsyncMock()):
            response = await client.post(
                "/api/analyses/analysis-1/decision/review",
                json={
                    "action": "override_action",
                    "override_action": "monitor",
                    "reason_code": "mission_priority",
                    "comments": "Temporary mission priority requires continued observation",
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["decision_status"] == "approved_for_use"
        assert payload["decision_summary"]["recommended_action"] == "monitor"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_decision_review_override_allowed_in_demo_mode(client, monkeypatch):
    mock_session = _MockSessionContext()
    analysis = _analysis()
    analysis_repo = AsyncMock()
    analysis_repo.get = AsyncMock(return_value=analysis)
    analysis_repo.update_decision_state = AsyncMock()
    audit_logs = AsyncMock()

    monkeypatch.setattr(settings, "AUTH_ENABLED", False)

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.AnalysisRepository", return_value=analysis_repo), \
         patch("db.repository.AuditLogRepository", return_value=audit_logs), \
         patch("services.webhook_service.dispatch_registered_webhooks", AsyncMock()):
        response = await client.post(
            "/api/analyses/analysis-1/decision/review",
            json={
                "action": "override_action",
                "override_action": "monitor",
                "reason_code": "new_evidence",
                "comments": "Demo override path should remain usable",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision_status"] == "approved_for_use"
    assert payload["decision_summary"]["recommended_action"] == "monitor"
