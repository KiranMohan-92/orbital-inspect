"""
API v1 router aggregator.

Mounts all business-logic sub-routers under the /api/v1 prefix.
Infrastructure endpoints (health, ready, metrics) remain unversioned on the app.
"""

from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1")


def mount_v1_routers() -> APIRouter:
    """Import and mount all sub-routers onto the v1 aggregator.

    Each sub-router uses a local prefix (e.g. ``/portfolio``) and the
    version prefix is supplied by ``v1_router``.
    """
    try:
        from api.reports import router as reports_router
        v1_router.include_router(reports_router)
    except ImportError:
        pass

    try:
        from api.webhooks import router as webhooks_router
        v1_router.include_router(webhooks_router)
    except ImportError:
        pass

    try:
        from api.precedents import router as precedents_router
        v1_router.include_router(precedents_router)
    except ImportError:
        pass

    try:
        from api.portfolio import router as portfolio_router
        v1_router.include_router(portfolio_router)
    except ImportError:
        pass

    try:
        from api.assets import router as assets_router
        v1_router.include_router(assets_router)
    except ImportError:
        pass

    try:
        from api.admin import router as admin_router
        v1_router.include_router(admin_router)
    except ImportError:
        pass

    try:
        from api.decisions import router as decisions_router
        v1_router.include_router(decisions_router)
    except ImportError:
        pass

    try:
        from api.datasets import router as datasets_router
        v1_router.include_router(datasets_router)
    except ImportError:
        pass

    try:
        from api.batch import router as batch_router
        v1_router.include_router(batch_router)
    except ImportError:
        pass

    return v1_router
