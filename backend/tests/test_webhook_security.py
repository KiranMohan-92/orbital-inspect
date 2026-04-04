import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

from api.webhooks import WebhookCreate, create_webhook
from auth.dependencies import CurrentUser
from config import settings
from services.secret_service import decrypt_webhook_secret, encrypt_webhook_secret, hash_secret
from services.webhook_service import dispatch_registered_webhooks


class _MockSessionContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def webhook_key(monkeypatch):
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(settings, "WEBHOOK_SECRET_ENCRYPTION_KEY", key)
    monkeypatch.setattr(settings, "WEBHOOK_SECRET_PREVIOUS_KEYS", [])
    return key


def test_encrypt_decrypt_webhook_secret_roundtrip(webhook_key):
    secret = "super-secret-webhook-key"

    ciphertext = encrypt_webhook_secret(secret)

    assert ciphertext != secret
    assert decrypt_webhook_secret(ciphertext) == secret


@pytest.mark.asyncio
async def test_create_webhook_persists_encrypted_secret_in_production(webhook_key, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    mock_session = _MockSessionContext()
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=SimpleNamespace(
        id="webhook-1",
        url="https://hooks.example.com/orbital",
        events=["analysis.completed"],
        active=True,
    ))
    body = WebhookCreate(
        url="https://hooks.example.com/orbital",
        secret="hook-secret",
        events=["analysis.completed"],
    )
    user = CurrentUser(user_id="admin-1", org_id="org-1", role="admin")

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.WebhookRepository", return_value=repo):
        response = await create_webhook(body, user=user)

    assert response["id"] == "webhook-1"
    persisted = repo.create.await_args.kwargs
    assert persisted["secret_hash"] == hash_secret("hook-secret")
    assert persisted["secret_ciphertext"] != "hook-secret"
    assert decrypt_webhook_secret(persisted["secret_ciphertext"]) == "hook-secret"


@pytest.mark.asyncio
async def test_dispatch_registered_webhooks_uses_decrypted_secret_and_records_delivery(webhook_key):
    mock_session = _MockSessionContext()
    webhook_repo = AsyncMock()
    webhook_repo.list_for_org = AsyncMock(return_value=[
        SimpleNamespace(
            id="webhook-1",
            url="https://hooks.example.com/orbital",
            events=["analysis.completed"],
            secret_ciphertext=encrypt_webhook_secret("hook-secret"),
        )
    ])
    delivery_repo = AsyncMock()
    dispatch_result = {
        "success": True,
        "status_code": 202,
        "attempt_count": 2,
        "response_excerpt": "accepted",
        "request_body_checksum": "checksum-123",
    }

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.WebhookRepository", return_value=webhook_repo), \
         patch("db.repository.WebhookDeliveryRepository", return_value=delivery_repo), \
         patch("services.webhook_service.dispatch_webhook", AsyncMock(return_value=dispatch_result)) as dispatch:
        await dispatch_registered_webhooks(
            org_id="org-1",
            event_type="analysis.completed",
            payload={"analysis_id": "analysis-1"},
        )

    dispatch.assert_awaited_once()
    assert dispatch.await_args.kwargs["secret"] == "hook-secret"
    delivery_repo.create.assert_awaited_once()
    persisted = delivery_repo.create.await_args.kwargs
    assert persisted["success"] is True
    assert persisted["status_code"] == 202
    assert persisted["attempt_count"] == 2
    assert persisted["request_body_checksum"] == "checksum-123"


@pytest.mark.asyncio
async def test_dispatch_registered_webhooks_fails_closed_on_invalid_ciphertext(webhook_key):
    mock_session = _MockSessionContext()
    webhook_repo = AsyncMock()
    webhook_repo.list_for_org = AsyncMock(return_value=[
        SimpleNamespace(
            id="webhook-1",
            url="https://hooks.example.com/orbital",
            events=["analysis.completed"],
            secret_ciphertext="invalid-ciphertext",
        )
    ])
    delivery_repo = AsyncMock()

    with patch("db.base.async_session_factory", return_value=mock_session), \
         patch("db.repository.WebhookRepository", return_value=webhook_repo), \
         patch("db.repository.WebhookDeliveryRepository", return_value=delivery_repo), \
         patch("services.webhook_service.dispatch_webhook", AsyncMock()) as dispatch:
        await dispatch_registered_webhooks(
            org_id="org-1",
            event_type="analysis.completed",
            payload={"analysis_id": "analysis-1"},
        )

    dispatch.assert_not_called()
    delivery_repo.create.assert_awaited_once()
    persisted = delivery_repo.create.await_args.kwargs
    assert persisted["success"] is False
    assert persisted["attempt_count"] == 0
    assert "Invalid encrypted webhook secret" in persisted["response_excerpt"]
