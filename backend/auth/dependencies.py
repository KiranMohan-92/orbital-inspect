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
import secrets
from fastapi import Request, HTTPException, Depends
from config import settings
from auth.jwt_service import decode_token, verify_role, AuthError
from services.distributed_rate_limiter import check_rate_limit

log = logging.getLogger(__name__)


class CurrentUser:
    """Represents the authenticated user from JWT or API key."""
    def __init__(
        self,
        user_id: str,
        org_id: str,
        role: str,
        auth_method: str = "jwt",
        rate_limit_per_hour: int | None = None,
    ):
        self.user_id = user_id
        self.org_id = org_id
        self.role = role
        self.auth_method = auth_method
        self.rate_limit_per_hour = rate_limit_per_hour


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
                rate_limit_per_hour=payload.get("rate_limit_per_hour"),
            )
        except AuthError as e:
            raise HTTPException(status_code=e.status_code, detail=e.message)

    # Try API key
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return await _validate_api_key(api_key)

    raise HTTPException(status_code=401, detail="Authentication required")


async def get_optional_current_user(request: Request) -> CurrentUser | None:
    """Best-effort auth lookup for endpoints that also accept machine credentials."""
    try:
        return await get_current_user(request)
    except HTTPException as exc:
        if exc.status_code == 401:
            return None
        raise


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
                rate_limit_per_hour=org.rate_limit_per_hour,
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


def require_observability_access():
    """
    Allow observability surfaces to be scraped by either:
    - an authenticated admin user, or
    - a shared machine token configured for internal collectors.
    """

    async def _check_access(
        request: Request,
        user: CurrentUser | None = Depends(get_optional_current_user),
    ):
        header_candidates = []
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            header_candidates.append(authorization[7:].strip())
        token_header = request.headers.get("X-Observability-Token", "").strip()
        if token_header:
            header_candidates.append(token_header)

        for candidate in header_candidates:
            for configured in settings.observability_tokens:
                if secrets.compare_digest(candidate, configured):
                    return CurrentUser(
                        user_id="system:observability",
                        org_id="system",
                        role="admin",
                        auth_method="observability_token",
                    )

        if user is None:
            if not settings.AUTH_ENABLED:
                return None
            raise HTTPException(status_code=401, detail="Authentication required")

        if not verify_role({"role": user.role}, "admin"):
            raise HTTPException(
                status_code=403,
                detail=f"Requires 'admin' role, you have '{user.role}'",
            )
        return user

    return _check_access


def require_rate_limit(limit_kind: str):
    async def _check_rate_limit(
        request: Request,
        user: CurrentUser | None = Depends(get_current_user),
    ):
        if settings.DEMO_MODE:
            return

        if limit_kind == "analysis":
            limit = user.rate_limit_per_hour if user and user.rate_limit_per_hour else settings.ANALYSIS_RATE_LIMIT_PER_HOUR
        else:
            limit = settings.REPORT_RATE_LIMIT_PER_HOUR

        subject = (
            f"org:{user.org_id}" if user and user.org_id else f"ip:{request.client.host if request.client else 'unknown'}"
        )
        allowed, info = await check_rate_limit(limit_kind, subject, limit=limit)
        request.state.rate_limit = info
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {limit_kind}",
                headers={"Retry-After": str(info["reset_seconds"])},
            )
    return _check_rate_limit
