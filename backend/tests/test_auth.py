"""Tests for authentication module."""

import os
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

import pytest
from auth.jwt_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_role,
    AuthError,
)
from auth.rate_limiter import RateLimiter


# ── JWT Tests ────────────────────────────────────────────────────────

def test_create_and_decode_access_token():
    token = create_access_token("user1", "org1", "analyst")
    payload = decode_token(token)
    assert payload["sub"] == "user1"
    assert payload["org_id"] == "org1"
    assert payload["role"] == "analyst"
    assert payload["type"] == "access"


def test_create_and_decode_refresh_token():
    token = create_refresh_token("user1", "org1")
    payload = decode_token(token)
    assert payload["sub"] == "user1"
    assert payload["type"] == "refresh"


def test_decode_invalid_token():
    with pytest.raises(AuthError, match="Invalid token"):
        decode_token("not.a.valid.token")


def test_decode_expired_token():
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta
    from config import settings

    payload = {
        "sub": "user1",
        "org_id": "org1",
        "role": "analyst",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "type": "access",
    }
    token = pyjwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    with pytest.raises(AuthError, match="expired"):
        decode_token(token)


def test_extra_claims_in_token():
    token = create_access_token("user1", "org1", "admin", extra_claims={"custom": "value"})
    payload = decode_token(token)
    assert payload["custom"] == "value"


# ── Role Hierarchy Tests ─────────────────────────────────────────────

def test_admin_has_all_roles():
    assert verify_role({"role": "admin"}, "viewer") is True
    assert verify_role({"role": "admin"}, "analyst") is True
    assert verify_role({"role": "admin"}, "admin") is True


def test_analyst_has_viewer_and_analyst():
    assert verify_role({"role": "analyst"}, "viewer") is True
    assert verify_role({"role": "analyst"}, "analyst") is True
    assert verify_role({"role": "analyst"}, "admin") is False


def test_viewer_has_only_viewer():
    assert verify_role({"role": "viewer"}, "viewer") is True
    assert verify_role({"role": "viewer"}, "analyst") is False
    assert verify_role({"role": "viewer"}, "admin") is False


def test_unknown_role_denied():
    assert verify_role({"role": "unknown"}, "viewer") is False


# ── Rate Limiter Tests ───────────────────────────────────────────────

def test_rate_limiter_allows_under_limit():
    limiter = RateLimiter(default_limit=5, window_seconds=60)
    allowed, info = limiter.check("test_key")
    assert allowed is True
    assert info["remaining"] == 4


def test_rate_limiter_blocks_over_limit():
    limiter = RateLimiter(default_limit=3, window_seconds=60)
    for _ in range(3):
        limiter.check("test_key")
    allowed, info = limiter.check("test_key")
    assert allowed is False
    assert info["remaining"] == 0


def test_rate_limiter_custom_limit():
    limiter = RateLimiter(default_limit=100, window_seconds=60)
    for _ in range(5):
        limiter.check("test_key", limit=5)
    allowed, info = limiter.check("test_key", limit=5)
    assert allowed is False


def test_rate_limiter_different_keys_independent():
    limiter = RateLimiter(default_limit=2, window_seconds=60)
    limiter.check("key_a")
    limiter.check("key_a")
    allowed_a, _ = limiter.check("key_a")
    allowed_b, _ = limiter.check("key_b")
    assert allowed_a is False
    assert allowed_b is True
