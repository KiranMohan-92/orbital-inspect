"""
API v1 router aggregator.

Mounts all business-logic sub-routers under the /api/v1 prefix.
Infrastructure endpoints (health, ready, metrics) remain unversioned on the app.
"""

from fastapi import APIRouter


def mount_v1_routers() -> APIRouter:
    """Import and mount all sub-routers onto the v1 aggregator.

    Each sub-router uses a local prefix (e.g. ``/portfolio``) and the
    version prefix is supplied by ``v1_router``.
    """
    v1_router = APIRouter(prefix="/api/v1")

    from api.reports import router as reports_router
    from api.webhooks import router as webhooks_router
    from api.precedents import router as precedents_router
    from api.portfolio import router as portfolio_router
    from api.assets import router as assets_router
    from api.admin import router as admin_router
    from api.decisions import router as decisions_router
    from api.datasets import router as datasets_router
    from api.batch import router as batch_router
    from api.trends import router as trends_router

    v1_router.include_router(reports_router)
    v1_router.include_router(webhooks_router)
    v1_router.include_router(precedents_router)
    v1_router.include_router(portfolio_router)
    v1_router.include_router(assets_router)
    v1_router.include_router(admin_router)
    v1_router.include_router(decisions_router)
    v1_router.include_router(datasets_router)
    v1_router.include_router(batch_router)
    v1_router.include_router(trends_router)

    return v1_router
