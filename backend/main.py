"""
Orbital Inspect — FastAPI backend with SSE streaming.

Endpoints:
  POST /api/analyze              — Upload satellite image, stream SSE events
  GET  /api/health               — Health check
  GET  /api/demos                — List demo cases
  POST /api/demo/{name}          — Run pre-cached demo analysis
  GET  /api/analyses             — List all analyses (paginated)
  GET  /api/analyses/{id}        — Get full analysis results
  GET  /api/analyses/{id}/events — Get SSE event audit trail
"""

import json
import re
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import settings
from agents.orchestrator import run_satellite_pipeline
from services.sse_service import format_sse_error

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """Application startup/shutdown."""
    # Initialize structured logging
    try:
        from services.logging_config import setup_logging
        setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    except ImportError:
        pass

    # Initialize database in demo mode (SQLite, auto-create tables)
    if settings.DEMO_MODE:
        try:
            from db.base import init_db
            await init_db()
            log.info("Database initialized (DEMO_MODE)")
        except ImportError:
            log.info("Database module not available, running without persistence")

    yield


app = FastAPI(
    title="Orbital Inspect",
    description="Satellite Condition Intelligence — AI-powered damage assessment for space insurers",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not settings.DEMO_MODE:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Request logging middleware
try:
    from middleware.request_logging import RequestLoggingMiddleware
    app.add_middleware(RequestLoggingMiddleware)
except ImportError:
    pass

# Mount API routers
try:
    from api.reports import router as reports_router
    app.include_router(reports_router)
except ImportError:
    pass

try:
    from api.webhooks import router as webhooks_router
    app.include_router(webhooks_router)
except ImportError:
    pass

try:
    from api.precedents import router as precedents_router
    app.include_router(precedents_router)
except ImportError:
    pass

try:
    from api.portfolio import router as portfolio_router
    app.include_router(portfolio_router)
except ImportError:
    pass


# ── Demo cache directory ─────────────────────────────────────────────
DEMO_DIR = Path(__file__).parent / "data" / "demo_cache"


# ── Health ───────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    from services.gemini_service import is_adk_available
    return {
        "status": "ok",
        "service": "orbital-inspect",
        "version": "0.2.0",
        "adk_available": is_adk_available(),
        "demo_mode": settings.DEMO_MODE,
    }


# ── Analyze (SSE streaming) ─────────────────────────────────────────
@app.post("/api/analyze")
async def analyze(
    image: UploadFile = File(...),
    norad_id: str = Form(default=""),
    context: str = Form(default=""),
):
    """
    Upload a satellite image and receive a streaming analysis via SSE.
    """
    content_type = image.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_bytes = await image.read()
    if len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image exceeds 20MB limit")

    norad = norad_id.strip() or None
    if norad and not re.fullmatch(r"\d{1,9}", norad):
        raise HTTPException(status_code=400, detail="norad_id must be 1-9 digits")

    async def event_generator():
        async for event in run_satellite_pipeline(
            image_bytes=image_bytes,
            image_mime=content_type,
            norad_id=norad,
            additional_context=context,
        ):
            yield event

    return EventSourceResponse(event_generator())


# ── Demo endpoints ───────────────────────────────────────────────────
DEMO_CONFIGS = {
    "hubble_solar_array": {
        "name": "Hubble Space Telescope — Solar Array",
        "norad_id": "20580",
        "description": "Micrometeorite impacts on HST solar array after 8+ years in LEO",
    },
    "iss_solar_panel": {
        "name": "ISS — Solar Panel Debris Strike",
        "norad_id": "25544",
        "description": "Orbital debris impact damage on ISS solar array wing",
    },
    "sentinel_1a": {
        "name": "Sentinel-1A — Particle Impact",
        "norad_id": "39634",
        "description": "~40cm affected area from particle impact on solar array",
    },
}


@app.get("/api/demos")
async def list_demos():
    """List available demo cases."""
    return {"demos": DEMO_CONFIGS}


@app.post("/api/demo/{demo_name}")
async def run_demo(demo_name: str):
    """Run a pre-configured demo analysis."""
    if demo_name not in DEMO_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Demo '{demo_name}' not found")

    config = DEMO_CONFIGS[demo_name]

    cache_path = DEMO_DIR / f"{demo_name}.json"
    if cache_path.exists():
        cached_events = json.loads(cache_path.read_text())

        async def cached_generator():
            import asyncio
            for event in cached_events:
                yield event
                await asyncio.sleep(0.3)

        return EventSourceResponse(cached_generator())

    image_dir = Path(__file__).parent / "data" / "demo_images"
    image_path = None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = image_dir / f"{demo_name}{ext}"
        if candidate.exists():
            image_path = candidate
            break

    if image_path is None:
        async def error_generator():
            yield format_sse_error(f"Demo image not available for '{demo_name}'.")
        return EventSourceResponse(error_generator())

    if image_path.stat().st_size > 20 * 1024 * 1024:
        raise HTTPException(status_code=500, detail="Demo image exceeds size limit")
    image_bytes = image_path.read_bytes()
    mime = f"image/{image_path.suffix.lstrip('.')}"
    if mime == "image/jpg":
        mime = "image/jpeg"

    async def demo_generator():
        async for event in run_satellite_pipeline(
            image_bytes=image_bytes,
            image_mime=mime,
            norad_id=config.get("norad_id"),
            additional_context=config.get("description", ""),
        ):
            yield event

    return EventSourceResponse(demo_generator())


# ── Analysis Results (persistent) ────────────────────────────────────
@app.get("/api/analyses")
async def list_analyses(limit: int = 20, offset: int = 0):
    """List all analyses with pagination."""
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            items, total = await repo.list_analyses(limit=limit, offset=offset)
            return {
                "items": [
                    {
                        "id": a.id,
                        "status": a.status,
                        "norad_id": a.norad_id,
                        "report_completeness": a.report_completeness,
                        "created_at": a.created_at.isoformat() if a.created_at else None,
                        "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                    }
                    for a in items
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
    except ImportError:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}


@app.get("/api/analyses/{analysis_id}")
async def get_analysis(analysis_id: str):
    """Get full analysis results by ID."""
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            analysis = await repo.get(analysis_id)
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")

            return {
                "id": analysis.id,
                "status": analysis.status,
                "norad_id": analysis.norad_id,
                "report_completeness": analysis.report_completeness,
                "evidence_gaps": analysis.evidence_gaps,
                "classification": analysis.classification_result,
                "vision": analysis.vision_result,
                "environment": analysis.environment_result,
                "failure_mode": analysis.failure_mode_result,
                "insurance_risk": analysis.insurance_risk_result,
                "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
                "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
            }
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@app.get("/api/analyses/{analysis_id}/events")
async def get_analysis_events(analysis_id: str):
    """Get all SSE events for an analysis (audit trail)."""
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            events = await repo.get_events(analysis_id)
            return {
                "analysis_id": analysis_id,
                "events": [
                    {
                        "agent": e.agent,
                        "status": e.status,
                        "payload": e.payload,
                        "sequence": e.sequence,
                        "degraded": e.degraded,
                        "created_at": e.created_at.isoformat() if e.created_at else None,
                    }
                    for e in events
                ],
            }
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


# ── Ensure data directories exist ────────────────────────────────────
(Path(__file__).parent / "data" / "demo_images").mkdir(parents=True, exist_ok=True)
(Path(__file__).parent / "data" / "demo_cache").mkdir(parents=True, exist_ok=True)
