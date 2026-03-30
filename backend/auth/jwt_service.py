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
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises AuthError on invalid/expired tokens.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthError(f"Invalid token: {e}")


def verify_role(token_payload: dict, required_role: str) -> bool:
    """
    Check if token has the required role.

    Role hierarchy: admin > analyst > viewer
    """
    hierarchy = {"viewer": 0, "analyst": 1, "admin": 2}
    user_level = hierarchy.get(token_payload.get("role", ""), -1)
    required_level = hierarchy.get(required_role, 0)
    return user_level >= required_level
