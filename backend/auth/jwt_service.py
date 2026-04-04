"""
JWT token service for authentication.

Handles token creation, validation, and refresh.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import jwt
from config import settings

log = logging.getLogger(__name__)

ALGORITHM = "HS256"


class AuthError(Exception):
    """Authentication/authorization error."""
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def create_access_token(
    user_id: str,
    org_id: str,
    role: str = "analyst",
    extra_claims: dict | None = None,
) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
        "type": "access",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token(user_id: str, org_id: str) -> str:
    """Create a JWT refresh token (7-day expiry)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "iat": now,
        "exp": now + timedelta(days=7),
        "type": "refresh",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def create_artifact_token(
    *,
    report_id: str,
    org_id: str | None,
    artifact_path: str,
    artifact_content_type: str,
    expires_minutes: int | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": report_id,
        "org_id": org_id,
        "artifact_path": artifact_path,
        "artifact_content_type": artifact_content_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes or settings.SIGNED_ARTIFACT_TTL_MINUTES),
        "type": "report_artifact",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises AuthError on invalid/expired tokens.
    """
    secrets = [settings.JWT_SECRET, *settings.JWT_PREVIOUS_SECRETS]
    last_error: Exception | None = None
    for secret in secrets:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[ALGORITHM],
                issuer=settings.JWT_ISSUER,
                audience=settings.JWT_AUDIENCE,
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthError("Token has expired")
        except jwt.InvalidTokenError as e:
            last_error = e
            continue
    raise AuthError(f"Invalid token: {last_error}")


def verify_role(token_payload: dict, required_role: str) -> bool:
    """
    Check if token has the required role.

    Role hierarchy: admin > analyst > viewer
    """
    hierarchy = {"viewer": 0, "analyst": 1, "admin": 2}
    user_level = hierarchy.get(token_payload.get("role", ""), -1)
    required_level = hierarchy.get(required_role, 0)
    return user_level >= required_level
