"""
FastAPI dependency injection for authentication.

Usage in endpoints:
    @app.get("/api/protected")
    async def protected(user=Depends(get_current_user)):
        ...

    @app.get("/api/admin-only")
    async def admin_only(user=Depends(require_role("admin"))):
        ...
"""

import logging
import hashlib
from fastapi import Request, HTTPException, Depends
from config import settings
from auth.jwt_service import decode_token, verify_role, AuthError

log = logging.getLogger(__name__)


class CurrentUser:
    """Represents the authenticated user from JWT or API key."""
    def __init__(self, user_id: str, org_id: str, role: str, auth_method: str = "jwt"):
        self.user_id = user_id
        self.org_id = org_id
        self.role = role
        self.auth_method = auth_method


async def get_current_user(request: Request) -> CurrentUser | None:
    """
    Extract and validate the current user from the request.

    Supports two auth methods:
    1. Bearer token in Authorization header (JWT)
    2. API key in X-API-Key header

    Returns None if AUTH_ENABLED is False (demo mode).
    """
    if not settings.AUTH_ENABLED:
        return None  # Auth disabled in demo mode

    # Try JWT first
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_token(token)
            return CurrentUser(
                user_id=payload["sub"],
                org_id=payload["org_id"],
                role=payload.get("role", "viewer"),
                auth_method="jwt",
            )
        except AuthError as e:
            raise HTTPException(status_code=e.status_code, detail=e.message)

    # Try API key
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return await _validate_api_key(api_key)

    raise HTTPException(status_code=401, detail="Authentication required")


async def _validate_api_key(api_key: str) -> CurrentUser:
    """Validate an API key against the database."""
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    try:
        from db.base import async_session_factory
        from db.models import Organization
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(
                select(Organization).where(
                    Organization.api_key_hash == key_hash,
                    Organization.active == True,
                )
            )
            org = result.scalar_one_or_none()
            if not org:
                raise HTTPException(status_code=401, detail="Invalid API key")

            return CurrentUser(
                user_id=f"apikey_{org.id}",
                org_id=org.id,
                role="analyst",  # API keys get analyst role by default
                auth_method="api_key",
            )
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available for API key auth")


def require_role(role: str):
    """
    Factory for role-based access control dependency.

    Usage: Depends(require_role("admin"))
    """
    async def _check_role(user: CurrentUser | None = Depends(get_current_user)):
        if user is None:
            return None  # Auth disabled
        if not verify_role({"role": user.role}, role):
            raise HTTPException(
                status_code=403,
                detail=f"Requires '{role}' role, you have '{user.role}'",
            )
        return user
    return _check_role
