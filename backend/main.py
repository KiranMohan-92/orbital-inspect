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

import asyncio
import json
import re
import logging
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from time import monotonic
from typing import Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import settings
from agents.orchestrator import run_satellite_pipeline
from services.sse_service import format_sse_error, format_sse_done
from services.metrics_service import (
    record_analysis_created,
    record_stream_close,
    record_stream_open,
    snapshot_metrics,
)
from auth.dependencies import get_current_user, require_role, CurrentUser

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
DEMO_DIR = settings.demo_cache_dir_path
DEMO_IMAGES_DIR = settings.demo_images_dir_path
UPLOAD_DIR = settings.uploads_dir_path
TERMINAL_ANALYSIS_STATUSES = {"completed", "completed_partial", "failed", "rejected"}
VALID_ASSET_TYPES = {
    "satellite",
    "servicer",
    "station_module",
    "solar_array",
    "radiator",
    "power_node",
    "compute_platform",
    "other",
}
BACKGROUND_TASKS: set[asyncio.Task] = set()


def _safe_json_form(value: str, field_name: str) -> dict[str, Any]:
    if not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail=f"{field_name} must decode to an object")
    return parsed


def _normalize_asset_type(value: str) -> str:
    asset_type = value.strip() or "satellite"
    if asset_type not in VALID_ASSET_TYPES:
        allowed = ", ".join(sorted(VALID_ASSET_TYPES))
        raise HTTPException(status_code=400, detail=f"asset_type must be one of: {allowed}")
    return asset_type


async def _collect_uploads(
    image: UploadFile | None,
    images: list[UploadFile] | None,
) -> list[tuple[UploadFile, bytes, str]]:
    uploads: list[UploadFile] = []
    if image is not None:
        uploads.append(image)
    if images:
        uploads.extend(images)

    if not uploads:
        raise HTTPException(status_code=400, detail="At least one image is required")

    collected: list[tuple[UploadFile, bytes, str]] = []
    for upload in uploads:
        content_type = upload.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        image_bytes = await upload.read()
        if len(image_bytes) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image exceeds 20MB limit")
        collected.append((upload, image_bytes, content_type))

    return collected


def _compute_evidence_completeness(bundle_summary: dict[str, Any]) -> float | None:
    sources = set(bundle_summary.get("sources_available") or [])
    if not sources:
        return 0.0
    required_sources = {
        "imagery",
        "tle_history",
        "conjunction_risk",
        "space_weather",
        "prior_analysis",
        "debris_environment",
    }
    return round((len(sources & required_sources) / len(required_sources)) * 100.0, 1)


async def _create_analysis_record(
    *,
    uploads: list[tuple[UploadFile, bytes, str]],
    norad: str | None,
    context: str,
    asset_type: str,
    inspection_epoch: str,
    target_subsystem: str,
    capture_metadata: dict[str, Any],
    telemetry_summary: dict[str, Any],
    baseline_reference: dict[str, Any],
    user: CurrentUser | None,
    request_id: str | None,
) -> str:
    from db.base import async_session_factory
    if settings.DEMO_MODE:
        from db.base import init_db
        await init_db()
    from db.repository import AnalysisRepository
    from workers.analysis_worker import run_analysis_job

    primary_upload, primary_bytes, primary_mime = uploads[0]
    suffix = Path(primary_upload.filename or "image.jpg").suffix or ".jpg"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    stored_path.write_bytes(primary_bytes)

    if settings.E2E_TEST_MODE:
        evidence_bundle_summary = {
            "satellite_id": norad or "e2e-test-asset",
            "satellite_name": "Deterministic E2E Asset",
            "total_items": 1,
            "sources_available": ["imagery"],
            "prior_analyses_count": 0,
            "prior_risk_tiers": [],
            "earliest_evidence": None,
            "latest_evidence": None,
            "inspection_epoch": inspection_epoch or None,
            "target_subsystem": target_subsystem or None,
        }
    else:
        from models.evidence import EvidenceItem, EvidenceSource
        from services.evidence_service import build_evidence_bundle

        evidence_bundle = await build_evidence_bundle(
            satellite_id=norad or "",
            norad_id=norad,
            org_id=user.org_id if user else None,
        )
        evidence_bundle.add_item(
            EvidenceItem(
                source=EvidenceSource.IMAGERY,
                data_type=primary_mime,
                description=f"Uploaded inspection imagery ({len(uploads)} file(s))",
                confidence=0.98,
                payload={
                    "image_count": len(uploads),
                    "primary_filename": primary_upload.filename or "",
                },
                metadata={"stored_path": str(stored_path)},
            )
        )
        evidence_bundle_summary = {
            "satellite_id": evidence_bundle.satellite_id,
            "satellite_name": evidence_bundle.satellite_name,
            "total_items": evidence_bundle.total_items,
            "sources_available": evidence_bundle.sources_available,
            "prior_analyses_count": evidence_bundle.prior_analyses_count,
            "prior_risk_tiers": evidence_bundle.prior_risk_tiers,
            "earliest_evidence": evidence_bundle.earliest_evidence,
            "latest_evidence": evidence_bundle.latest_evidence,
            "inspection_epoch": inspection_epoch or None,
            "target_subsystem": target_subsystem or None,
        }

    async with async_session_factory() as session:
        repo = AnalysisRepository(session)
        analysis = await repo.create(
            org_id=user.org_id if user else None,
            image_bytes=primary_bytes,
            image_path=str(stored_path),
            norad_id=norad,
            additional_context=context,
            request_id=request_id,
            asset_type=asset_type,
            inspection_epoch=inspection_epoch or None,
            target_subsystem=target_subsystem or None,
            capture_metadata={
                **capture_metadata,
                "image_count": len(uploads),
                "filenames": [upload.filename or "" for upload, _bytes, _mime in uploads],
            },
            telemetry_summary=telemetry_summary,
            baseline_reference=baseline_reference,
            evidence_bundle_summary=evidence_bundle_summary,
            evidence_completeness_pct=_compute_evidence_completeness(evidence_bundle_summary),
        )

    task = asyncio.create_task(
        run_analysis_job(
            {},
            analysis.id,
            primary_bytes,
            primary_mime,
            norad,
            context,
        )
    )
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(BACKGROUND_TASKS.discard)
    return analysis.id


async def _stream_analysis_events_generator(
    analysis_id: str,
    user: CurrentUser | None,
):
    from db.base import async_session_factory
    from db.repository import AnalysisRepository

    last_sequence = -1
    events_emitted = 0
    stream_started = monotonic()
    terminal_status = "closed"
    record_stream_open()

    try:
        while True:
            async with async_session_factory() as session:
                repo = AnalysisRepository(session)
                analysis = await repo.get(analysis_id, org_id=user.org_id if user else None)
                if not analysis:
                    terminal_status = "not_found"
                    yield format_sse_error("Analysis not found")
                    return

                events = await repo.get_events(analysis_id)
                for event in events:
                    if event.sequence <= last_sequence:
                        continue
                    last_sequence = event.sequence
                    events_emitted += 1
                    payload = {
                        "agent": event.agent,
                        "status": event.status,
                        "payload": event.payload or {},
                        "timestamp": int(event.created_at.timestamp() * 1000) if event.created_at else 0,
                        "analysis_id": analysis_id,
                        "event_id": event.id,
                        "sequence": event.sequence,
                        "schema_version": "2.0",
                        "degraded": event.degraded,
                    }
                    yield {"event": "agent_event", "data": json.dumps(payload)}

                if analysis.status in TERMINAL_ANALYSIS_STATUSES:
                    terminal_status = analysis.status
                    yield format_sse_done(analysis.status)
                    return

            await asyncio.sleep(0.35)
    finally:
        record_stream_close(
            terminal_status,
            duration_ms=(monotonic() - stream_started) * 1000.0,
            events_emitted=events_emitted,
        )


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


@app.get("/api/metrics")
async def metrics(user: CurrentUser | None = Depends(require_role("admin"))):
    return snapshot_metrics()


# ── Durable analysis submission ─────────────────────────────────────
@app.post("/api/analyses")
async def create_analysis(
    request: Request,
    image: UploadFile | None = File(default=None),
    images: list[UploadFile] | None = File(default=None),
    norad_id: str = Form(default=""),
    context: str = Form(default=""),
    asset_type: str = Form(default="satellite"),
    inspection_epoch: str = Form(default=""),
    target_subsystem: str = Form(default=""),
    capture_metadata: str = Form(default=""),
    telemetry_summary: str = Form(default=""),
    baseline_reference: str = Form(default=""),
    user: CurrentUser | None = Depends(require_role("analyst")),
):
    """Create a persisted analysis job and return resource URLs."""
    uploads = await _collect_uploads(image, images)

    norad = norad_id.strip() or None
    if norad and not re.fullmatch(r"\d{1,9}", norad):
        raise HTTPException(status_code=400, detail="norad_id must be 1-9 digits")
    normalized_asset_type = _normalize_asset_type(asset_type)

    analysis_id = await _create_analysis_record(
        uploads=uploads,
        norad=norad,
        context=context,
        asset_type=normalized_asset_type,
        inspection_epoch=inspection_epoch.strip(),
        target_subsystem=target_subsystem.strip(),
        capture_metadata=_safe_json_form(capture_metadata, "capture_metadata"),
        telemetry_summary=_safe_json_form(telemetry_summary, "telemetry_summary"),
        baseline_reference=_safe_json_form(baseline_reference, "baseline_reference"),
        user=user,
        request_id=getattr(request.state, "request_id", None),
    )
    record_analysis_created(normalized_asset_type)

    return {
        "analysis_id": analysis_id,
        "status": "queued",
        "analysis_url": f"/api/analyses/{analysis_id}",
        "events_url": f"/api/analyses/{analysis_id}/events/stream",
        "request_id": getattr(request.state, "request_id", None),
    }


# ── Legacy analyze stream wrapper ───────────────────────────────────
@app.post("/api/analyze")
async def analyze(
    image: UploadFile = File(...),
    norad_id: str = Form(default=""),
    context: str = Form(default=""),
    asset_type: str = Form(default="satellite"),
    inspection_epoch: str = Form(default=""),
    target_subsystem: str = Form(default=""),
    capture_metadata: str = Form(default=""),
    telemetry_summary: str = Form(default=""),
    baseline_reference: str = Form(default=""),
    user: CurrentUser | None = Depends(require_role("analyst")),
):
    """
    Legacy wrapper: preserve inline SSE behavior for one transition window.
    """
    uploads = await _collect_uploads(image, None)
    _safe_json_form(capture_metadata, "capture_metadata")
    _safe_json_form(telemetry_summary, "telemetry_summary")
    _safe_json_form(baseline_reference, "baseline_reference")
    _normalize_asset_type(asset_type)
    inspection_epoch.strip()
    target_subsystem.strip()

    norad = norad_id.strip() or None
    if norad and not re.fullmatch(r"\d{1,9}", norad):
        raise HTTPException(status_code=400, detail="norad_id must be 1-9 digits")

    _upload, image_bytes, content_type = uploads[0]

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

    image_dir = DEMO_IMAGES_DIR
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
async def list_analyses(
    limit: int = 20,
    offset: int = 0,
    user: CurrentUser | None = Depends(get_current_user),
):
    """List all analyses with pagination."""
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            items, total = await repo.list_analyses(
                org_id=user.org_id if user else None,
                limit=limit,
                offset=offset,
            )
            return {
                "items": [
                    {
                        "id": a.id,
                        "status": a.status,
                        "asset_type": getattr(a, "asset_type", "satellite"),
                        "request_id": getattr(a, "request_id", None),
                        "inspection_epoch": getattr(a, "inspection_epoch", None),
                        "target_subsystem": getattr(a, "target_subsystem", None),
                        "norad_id": a.norad_id,
                        "degraded": getattr(a, "degraded", False),
                        "failure_reasons": getattr(a, "failure_reasons", []) or [],
                        "report_completeness": a.report_completeness,
                        "evidence_completeness_pct": getattr(a, "evidence_completeness_pct", None),
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
async def get_analysis(
    analysis_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Get full analysis results by ID."""
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            analysis = await repo.get(analysis_id, org_id=user.org_id if user else None)
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")

            return {
                "id": analysis.id,
                "status": analysis.status,
                "asset_type": getattr(analysis, "asset_type", "satellite"),
                "request_id": getattr(analysis, "request_id", None),
                "inspection_epoch": getattr(analysis, "inspection_epoch", None),
                "target_subsystem": getattr(analysis, "target_subsystem", None),
                "norad_id": analysis.norad_id,
                "additional_context": getattr(analysis, "additional_context", ""),
                "capture_metadata": getattr(analysis, "capture_metadata", {}) or {},
                "telemetry_summary": getattr(analysis, "telemetry_summary", {}) or {},
                "baseline_reference": getattr(analysis, "baseline_reference", {}) or {},
                "degraded": getattr(analysis, "degraded", False),
                "failure_reasons": getattr(analysis, "failure_reasons", []) or [],
                "report_completeness": analysis.report_completeness,
                "evidence_completeness_pct": getattr(analysis, "evidence_completeness_pct", None),
                "evidence_bundle_summary": getattr(analysis, "evidence_bundle_summary", {}) or {},
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


@app.get("/api/analyses/{analysis_id}/events/stream")
async def stream_analysis_events(
    analysis_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Stream persisted analysis events via SSE."""
    return EventSourceResponse(_stream_analysis_events_generator(analysis_id, user))


@app.get("/api/analyses/{analysis_id}/events")
async def get_analysis_events(
    analysis_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Get all SSE events for an analysis (audit trail)."""
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            analysis = await repo.get(analysis_id, org_id=user.org_id if user else None)
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")
            events = await repo.get_events(analysis_id)
            return {
                "analysis_id": analysis_id,
                "status": getattr(analysis, "status", "unknown"),
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
settings.demo_images_dir_path.mkdir(parents=True, exist_ok=True)
settings.demo_cache_dir_path.mkdir(parents=True, exist_ok=True)
settings.uploads_dir_path.mkdir(parents=True, exist_ok=True)
