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
from pathlib import Path
from contextlib import asynccontextmanager
from time import monotonic
from typing import Any
from io import BytesIO
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse

from config import settings
from agents.orchestrator import run_satellite_pipeline
from services.sse_service import format_sse_error, format_sse_done
from services.metrics_service import (
    record_analysis_created,
    record_stream_close,
    record_stream_open,
    snapshot_metrics,
)
from services.governance_service import build_model_manifest
from services.observability_service import setup_observability, shutdown_observability, telemetry_state
from services.queue_service import enqueue_analysis_job, should_use_queue_dispatch
from services.readiness_service import readiness_snapshot
from services.storage_service import get_storage_backend
from services.assessment_mode_service import build_assessment_contract, normalize_assessment_mode
from auth.dependencies import (
    get_current_user,
    require_observability_access,
    require_role,
    require_rate_limit,
    CurrentUser,
)

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

    setup_observability(app=app, service_version="0.2.0")

    # Initialize database when running demo, E2E, or service-backed ephemeral environments.
    if settings.DEMO_MODE or settings.DATABASE_AUTO_INIT or settings.E2E_TEST_MODE:
        try:
            from db.base import init_db
            from services.post_analysis_service import backfill_decisions
            from db.base import async_session_factory
            await init_db()
            async with async_session_factory() as session:
                backfilled = await backfill_decisions(session=session, limit=5000)
            log.info(
                "Database initialized",
                extra={
                    "demo_mode": settings.DEMO_MODE,
                    "database_auto_init": settings.DATABASE_AUTO_INIT,
                    "backfilled_decisions": backfilled,
                },
            )
        except ImportError:
            log.info("Database module not available, running without persistence")

    yield
    shutdown_observability()


app = FastAPI(
    title="Orbital Inspect",
    description="Public-source satellite risk intelligence and evidence triage for orbital asset operators and insurers",
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

# ── Backward-compat redirect: /api/<path> → /api/v1/<path> ─────────
# Infrastructure endpoints (health, ready, metrics) are excluded.
_UNVERSIONED_PREFIXES = ("/api/health", "/api/ready", "/api/metrics")


class ApiVersionRedirectMiddleware(BaseHTTPMiddleware):
    """Transparently rewrite legacy /api/X requests to /api/v1/X."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.scope["path"]
        if (
            path.startswith("/api/")
            and not path.startswith("/api/v1/")
            and not any(path.startswith(p) for p in _UNVERSIONED_PREFIXES)
        ):
            # Rewrite path in-place (internal redirect, no 301/302)
            new_path = "/api/v1/" + path[len("/api/"):]
            request.scope["path"] = new_path
        return await call_next(request)


app.add_middleware(ApiVersionRedirectMiddleware)

# Register RFC 7807 error envelope
from api.error_envelope import register_error_handlers
register_error_handlers(app)

# Request logging middleware
from middleware.request_logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)

# Mount versioned API router (all business endpoints under /api/v1/)
from api.v1 import mount_v1_routers
v1_router = mount_v1_routers()
app.include_router(v1_router)


# ── Demo cache directory ─────────────────────────────────────────────
DEMO_DIR = settings.demo_cache_dir_path
DEMO_IMAGES_DIR = settings.demo_images_dir_path
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
LEGACY_ANALYZE_SUNSET = "Tue, 30 Jun 2026 00:00:00 GMT"


def _legacy_analyze_headers() -> dict[str, str]:
    return {
        "Deprecation": "true",
        "Sunset": LEGACY_ANALYZE_SUNSET,
        "Link": '</api/v1/analyses>; rel="successor-version"',
        "X-Orbital-Legacy-Endpoint": "true",
    }


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

    if len(uploads) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple images are not supported yet; submit one primary image per analysis",
        )

    collected: list[tuple[UploadFile, bytes, str]] = []
    for upload in uploads:
        content_type = upload.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        image_bytes = await upload.read()
        if len(image_bytes) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image exceeds 20MB limit")
        sanitized_bytes, sanitized_content_type = _sanitize_image_upload(image_bytes)
        collected.append((upload, sanitized_bytes, sanitized_content_type))

    return collected


def _sanitize_image_upload(image_bytes: bytes) -> tuple[bytes, str]:
    strict_decode = settings.APP_ENV in {"staging", "production"} and not settings.DEMO_MODE
    if not strict_decode:
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return image_bytes, "image/jpeg"
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return image_bytes, "image/png"
        if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            return image_bytes, "image/webp"

    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Image validation backend unavailable") from exc

    try:
        with Image.open(BytesIO(image_bytes)) as img:
            img.load()
            width, height = img.size
            if width <= 0 or height <= 0 or width > 12000 or height > 12000:
                raise HTTPException(status_code=400, detail="Image dimensions are outside allowed bounds")
            fmt = (img.format or "").upper()
            if fmt not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(status_code=400, detail="Unsupported image format")
            output = BytesIO()
            if fmt == "JPEG":
                safe_img = img.convert("RGB")
                safe_img.save(output, format="JPEG", quality=95, optimize=True)
                return output.getvalue(), "image/jpeg"
            safe_img = img.convert("RGBA") if img.mode not in {"RGB", "RGBA"} else img.copy()
            safe_img.save(output, format="PNG", optimize=True)
            return output.getvalue(), "image/png"
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="File is not a valid decodable image") from exc


REQUIRED_DECISION_EVIDENCE_SOURCES = {
    "imagery",
    "tle_history",
    "conjunction_risk",
    "space_weather",
    "debris_environment",
}


def _assessment_contract_or_400(
    *,
    assessment_mode: str,
    capture_metadata: dict[str, Any],
    telemetry_summary: dict[str, Any],
    baseline_reference: dict[str, Any],
    evidence_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        contract = build_assessment_contract(
            assessment_mode=assessment_mode,
            capture_metadata=capture_metadata,
            telemetry_summary=telemetry_summary,
            baseline_reference=baseline_reference,
            evidence_quality=evidence_quality,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if (
        contract["assessment_mode"] == "UNDERWRITING_GRADE"
        and contract["decision_authority"] != "UNDERWRITING_REVIEW"
    ):
        missing = ", ".join(gap["label"] for gap in contract["required_evidence_gaps"])
        raise HTTPException(
            status_code=400,
            detail=f"UNDERWRITING_GRADE requires missing evidence classes: {missing}",
        )
    return contract


def _compute_evidence_completeness(bundle_summary: dict[str, Any]) -> float | None:
    quality = bundle_summary.get("evidence_quality")
    if isinstance(quality, dict) and quality.get("quality_score") is not None:
        return float(quality["quality_score"])

    sources = set(bundle_summary.get("sources_available") or [])
    if not sources:
        return 0.0
    return round((len(sources & REQUIRED_DECISION_EVIDENCE_SOURCES) / len(REQUIRED_DECISION_EVIDENCE_SOURCES)) * 100.0, 1)


def _prom_escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _prom_labels(**labels: object) -> str:
    return ",".join(f'{key}="{_prom_escape(value)}"' for key, value in labels.items() if value is not None)


async def _create_analysis_record(
    *,
    uploads: list[tuple[UploadFile, bytes, str]],
    norad: str | None,
    context: str,
    asset_type: str,
    asset_name: str,
    external_asset_id: str,
    inspection_epoch: str,
    target_subsystem: str,
    capture_metadata: dict[str, Any],
    telemetry_summary: dict[str, Any],
    baseline_reference: dict[str, Any],
    assessment_mode: str,
    user: CurrentUser | None,
    request_id: str | None,
) -> dict[str, str]:
    from db.base import async_session_factory
    if settings.DEMO_MODE:
        from db.base import init_db
        await init_db()
    from db.repository import AnalysisRepository
    from db.repository import AuditLogRepository

    primary_upload, primary_bytes, primary_mime = uploads[0]
    storage = get_storage_backend()
    asset_name = asset_name.strip()
    external_asset_id = external_asset_id.strip()
    enriched_capture_metadata = {
        **capture_metadata,
        "asset_name": asset_name or capture_metadata.get("asset_name") or "",
        "external_asset_id": external_asset_id or capture_metadata.get("external_asset_id") or "",
        "assessment_mode": normalize_assessment_mode(assessment_mode).value,
    }
    enriched_baseline_reference = {
        **baseline_reference,
        "asset_name": asset_name or baseline_reference.get("asset_name") or "",
        "external_asset_id": external_asset_id or baseline_reference.get("external_asset_id") or "",
    }
    stored_object = storage.store_bytes(
        category="uploads",
        filename=primary_upload.filename or "image.jpg",
        data=primary_bytes,
        content_type=primary_mime,
        metadata={
            "norad_id": norad or "",
            "asset_type": asset_type,
            "asset_name": asset_name,
            "external_asset_id": external_asset_id,
            "request_id": request_id or "",
        },
    )

    evidence_bundle = None
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
            "assessment_mode": enriched_capture_metadata["assessment_mode"],
            "evidence_quality": {
                "quality_score": 20.0,
                "required_sources": sorted(REQUIRED_DECISION_EVIDENCE_SOURCES),
                "present_required_sources": ["imagery"],
                "missing_required_sources": sorted(REQUIRED_DECISION_EVIDENCE_SOURCES - {"imagery"}),
                "gaps": [
                    {
                        "source": source,
                        "status": "missing",
                        "description": f"Required evidence source {source} is not loaded in deterministic E2E mode",
                        "required_for_decision": True,
                        "mission_relevance": "critical",
                    }
                    for source in sorted(REQUIRED_DECISION_EVIDENCE_SOURCES - {"imagery"})
                ],
                "failed_source_count": 0,
                "stale_source_count": 0,
                "low_confidence_count": 0,
                "source_freshness": {},
            },
        }
        assessment_contract = build_assessment_contract(
            assessment_mode=enriched_capture_metadata["assessment_mode"],
            capture_metadata=enriched_capture_metadata,
            telemetry_summary=telemetry_summary,
            baseline_reference=enriched_baseline_reference,
            evidence_quality=evidence_bundle_summary["evidence_quality"],
        )
        evidence_bundle_summary["assessment_contract"] = assessment_contract
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
                metadata={"storage_uri": stored_object.uri},
            )
        )
        evidence_quality = evidence_bundle.quality_summary(REQUIRED_DECISION_EVIDENCE_SOURCES)
        assessment_contract = build_assessment_contract(
            assessment_mode=enriched_capture_metadata["assessment_mode"],
            capture_metadata=enriched_capture_metadata,
            telemetry_summary=telemetry_summary,
            baseline_reference=enriched_baseline_reference,
            evidence_quality=evidence_quality,
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
            "assessment_mode": enriched_capture_metadata["assessment_mode"],
            "evidence_quality": evidence_quality,
            "assessment_contract": assessment_contract,
        }

    async with async_session_factory() as session:
        from db.repository import AssetRepository

        repo = AnalysisRepository(session)
        assets = AssetRepository(session)
        audit_logs = AuditLogRepository(session)
        asset_alias_candidates = {
            "operator_asset_id": (
                enriched_baseline_reference.get("operator_asset_id")
                or enriched_capture_metadata.get("operator_asset_id")
            ),
            "cospar": (
                enriched_baseline_reference.get("cospar_id")
                or enriched_baseline_reference.get("international_designator")
                or enriched_capture_metadata.get("cospar_id")
                or enriched_capture_metadata.get("international_designator")
            ),
            "satcat": (
                enriched_baseline_reference.get("satcat_id")
                or enriched_capture_metadata.get("satcat_id")
            ),
            "manufacturer_designation": (
                enriched_baseline_reference.get("manufacturer_designation")
                or enriched_baseline_reference.get("platform")
            ),
        }
        asset = await assets.resolve_or_create(
            org_id=user.org_id if user else None,
            norad_id=norad,
            external_asset_id=external_asset_id or None,
            asset_type=asset_type,
            name=asset_name or enriched_baseline_reference.get("asset_name"),
            operator_name=(enriched_baseline_reference or {}).get("operator_name"),
            alias_candidates=asset_alias_candidates,
        )
        subsystem = await assets.resolve_or_create_subsystem(
            asset_id=asset.id,
            org_id=user.org_id if user else None,
            subsystem_key=target_subsystem or None,
            display_name=target_subsystem or None,
            subsystem_type=target_subsystem or None,
        )
        analysis = await repo.create(
            org_id=user.org_id if user else None,
            asset_id=asset.id,
            image_bytes=primary_bytes,
            image_path=stored_object.uri,
            norad_id=norad,
            additional_context=context,
            request_id=request_id,
            asset_type=asset_type,
            inspection_epoch=inspection_epoch or None,
            target_subsystem=target_subsystem or None,
            capture_metadata={
                **enriched_capture_metadata,
                "image_count": len(uploads),
                "filenames": [upload.filename or "" for upload, _bytes, _mime in uploads],
            },
            telemetry_summary=telemetry_summary,
            baseline_reference=enriched_baseline_reference,
            evidence_bundle_summary=evidence_bundle_summary,
            evidence_completeness_pct=_compute_evidence_completeness(evidence_bundle_summary),
            queue_name=settings.ANALYSIS_QUEUE_NAME,
            dispatch_mode="arq" if should_use_queue_dispatch() else "inline",
            max_retries=settings.ANALYSIS_JOB_MAX_RETRIES,
            governance_policy_version=settings.GOVERNANCE_POLICY_VERSION,
            model_manifest=build_model_manifest(),
            human_review_required=settings.REQUIRE_HUMAN_REVIEW_FOR_DECISIONS,
        )
        if subsystem:
            await repo.update_fields(analysis.id, subsystem_id=subsystem.id)
        if evidence_bundle is not None:
            from services.evidence_ingest_service import persist_evidence_bundle

            linked_evidence_count = await persist_evidence_bundle(
                session,
                analysis_id=analysis.id,
                org_id=user.org_id if user else None,
                asset_id=asset.id,
                subsystem_id=subsystem.id if subsystem else None,
                bundle=evidence_bundle,
            )
            await repo.update_fields(
                analysis.id,
                evidence_bundle_summary={
                    **evidence_bundle_summary,
                    "linked_evidence_count": linked_evidence_count,
                },
            )
            evidence_bundle_summary["linked_evidence_count"] = linked_evidence_count
        await audit_logs.create(
            org_id=user.org_id if user else None,
            actor_id=user.user_id if user else "anonymous",
            action="analysis.created",
            resource_type="analysis",
            resource_id=analysis.id,
            metadata_json={
                "asset_type": asset_type,
                "assessment_mode": enriched_capture_metadata["assessment_mode"],
                "asset_id": asset.id,
                "external_asset_id": external_asset_id or None,
                "subsystem_id": subsystem.id if subsystem else None,
                "dispatch_mode": "arq" if should_use_queue_dispatch() else "inline",
                "request_id": request_id,
            },
            analysis_id=analysis.id,
        )

    return {
        "analysis_id": analysis.id,
        "assessment_mode": enriched_capture_metadata["assessment_mode"],
        "decision_authority": evidence_bundle_summary.get("assessment_contract", {}).get("decision_authority", "SCREENING_ONLY"),
        "primary_mime": primary_mime,
        "primary_filename": primary_upload.filename or "image.jpg",
    }


async def _dispatch_analysis(
    *,
    analysis_id: str,
) -> dict[str, str]:
    from db.base import async_session_factory
    from db.repository import AnalysisRepository, AuditLogRepository

    if should_use_queue_dispatch():
        try:
            queue_job_id = await enqueue_analysis_job(analysis_id)
        except Exception as exc:
            async with async_session_factory() as session:
                repo = AnalysisRepository(session)
                audit_logs = AuditLogRepository(session)
                await repo.update_status(
                    analysis_id,
                    "failed",
                    degraded=True,
                    failure_reasons=[str(exc)],
                    last_error=str(exc),
                )
                await audit_logs.create(
                    org_id=None,
                    actor_id="system:dispatcher",
                    action="analysis.dispatch_failed",
                    resource_type="analysis",
                    resource_id=analysis_id,
                    metadata_json={"error": str(exc)},
                    analysis_id=analysis_id,
                )
            raise HTTPException(status_code=503, detail="Analysis queue unavailable") from exc

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            audit_logs = AuditLogRepository(session)
            analysis = await repo.get(analysis_id)
            await repo.mark_dispatched(
                analysis_id,
                queue_job_id=queue_job_id,
                dispatch_mode="arq",
                queue_name=settings.ANALYSIS_QUEUE_NAME,
            )
            await audit_logs.create(
                org_id=analysis.org_id if analysis else None,
                actor_id="system:dispatcher",
                action="analysis.dispatched",
                resource_type="analysis",
                resource_id=analysis_id,
                metadata_json={"queue_job_id": queue_job_id, "queue_name": settings.ANALYSIS_QUEUE_NAME},
                analysis_id=analysis_id,
            )
        return {"dispatch_mode": "arq", "queue_job_id": queue_job_id}

    from workers.analysis_worker import run_analysis_job

    task = asyncio.create_task(
        run_analysis_job(
            {},
            analysis_id,
        )
    )
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(BACKGROUND_TASKS.discard)

    async with async_session_factory() as session:
        repo = AnalysisRepository(session)
        audit_logs = AuditLogRepository(session)
        analysis = await repo.get(analysis_id)
        await repo.mark_dispatched(
            analysis_id,
            queue_job_id=f"inline:{analysis_id}",
            dispatch_mode="inline",
            queue_name="inline",
        )
        await audit_logs.create(
            org_id=analysis.org_id if analysis else None,
            actor_id="system:inline-dispatcher",
            action="analysis.dispatched",
            resource_type="analysis",
            resource_id=analysis_id,
            metadata_json={"queue_job_id": f"inline:{analysis_id}", "queue_name": "inline"},
            analysis_id=analysis_id,
        )
    return {"dispatch_mode": "inline", "queue_job_id": f"inline:{analysis_id}"}


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
    database_backend = "postgresql" if "postgres" in settings.DATABASE_URL else "sqlite"
    return {
        "status": "ok",
        "service": "orbital-inspect",
        "version": "0.2.0",
        "adk_available": is_adk_available(),
        "demo_mode": settings.DEMO_MODE,
        "database_backend": database_backend,
        "storage_backend": settings.STORAGE_BACKEND,
        "observability": telemetry_state(),
    }


@app.get("/api/ready")
async def ready(user: CurrentUser | None = Depends(require_observability_access())):
    snapshot = await readiness_snapshot()
    if not snapshot["ok"]:
        raise HTTPException(status_code=503, detail=snapshot)
    return snapshot


@app.get("/api/metrics")
async def metrics(user: CurrentUser | None = Depends(require_observability_access())):
    snapshot = snapshot_metrics()
    snapshot["observability"] = telemetry_state()
    return snapshot


@app.get("/api/metrics/prometheus")
async def prometheus_metrics(user: CurrentUser | None = Depends(require_observability_access())):
    if not settings.PROMETHEUS_METRICS_ENABLED:
        raise HTTPException(status_code=404, detail="Prometheus metrics disabled")
    snapshot = snapshot_metrics()
    observability = telemetry_state()
    lines = []
    for key, value in snapshot["requests"]["counts"].items():
        lines.append(f'orbital_requests_total{{key="{_prom_escape(key)}"}} {value}')
    for key, value in snapshot["requests"]["latency_ms"].items():
        method, _, path = key.partition("|")
        labels = _prom_labels(method=method, path=path)
        lines.append(f"orbital_request_latency_avg_ms{{{labels}}} {value['avg']}")
        lines.append(f"orbital_request_latency_max_ms{{{labels}}} {value['max']}")
    for key, value in snapshot["analyses"]["created"].items():
        _created, _, asset_type = key.partition("|")
        lines.append(f'orbital_analysis_created_total{{asset_type="{_prom_escape(asset_type)}"}} {value}')
    for key, value in snapshot["analyses"]["terminal"].items():
        lines.append(f'orbital_analysis_terminal_total{{status="{_prom_escape(key)}"}} {value}')
    for key, value in snapshot["analyses"]["retries"].items():
        lines.append(f'orbital_analysis_retries_total{{status="{_prom_escape(key)}"}} {value}')
    for key, value in snapshot["analyses"]["dead_letters"].items():
        lines.append(f'orbital_analysis_dead_letters_total{{reason="{_prom_escape(key)}"}} {value}')
    for key, value in snapshot["analyses"]["agent_events"].items():
        agent, _, remainder = key.partition("|")
        status, _, mode = remainder.partition("|")
        labels = _prom_labels(agent=agent, status=status, mode=mode)
        lines.append(f"orbital_agent_events_total{{{labels}}} {value}")
    for key, value in snapshot["analyses"]["stage_latency_ms"].items():
        labels = _prom_labels(agent=key)
        lines.append(f"orbital_stage_latency_avg_ms{{{labels}}} {value['avg']}")
        lines.append(f"orbital_stage_latency_max_ms{{{labels}}} {value['max']}")
    for key, value in snapshot["artifacts"].items():
        lines.append(f'orbital_report_artifacts_total{{kind="{_prom_escape(key)}"}} {value}')
    for key, value in snapshot["rate_limits"].items():
        lines.append(f'orbital_rate_limit_hits_total{{bucket="{_prom_escape(key)}"}} {value}')
    lines.append(f'orbital_active_streams {snapshot["streams"]["active"]}')
    for key, value in snapshot["streams"]["counts"].items():
        lines.append(f'orbital_streams_total{{status="{_prom_escape(key)}"}} {value}')
    lines.append(f'orbital_stream_duration_avg_ms {snapshot["streams"]["duration_ms"]["avg"]}')
    lines.append(f'orbital_stream_duration_max_ms {snapshot["streams"]["duration_ms"]["max"]}')
    lines.append(f'orbital_stream_events_avg {snapshot["streams"]["events_per_stream"]["avg"]}')
    lines.append(f'orbital_stream_events_max {snapshot["streams"]["events_per_stream"]["max"]}')
    lines.append(f'orbital_observability_enabled {1 if observability.get("enabled") else 0}')
    lines.append(f'orbital_observability_instrumented {1 if observability.get("instrumented") else 0}')
    lines.append(
        f'orbital_observability_exporter_info{{service="{_prom_escape(observability.get("service_name"))}",'
        f'exporter="{_prom_escape(observability.get("exporter"))}"}} 1'
    )
    return PlainTextResponse("\n".join(lines) + "\n")


# ── Durable analysis submission ─────────────────────────────────────
@app.post("/api/v1/analyses")
async def create_analysis(
    request: Request,
    image: UploadFile | None = File(default=None),
    images: list[UploadFile] | None = File(default=None),
    norad_id: str = Form(default=""),
    context: str = Form(default=""),
    asset_type: str = Form(default="satellite"),
    asset_name: str = Form(default=""),
    external_asset_id: str = Form(default=""),
    inspection_epoch: str = Form(default=""),
    target_subsystem: str = Form(default=""),
    assessment_mode: str = Form(default="PUBLIC_SCREEN"),
    capture_metadata: str = Form(default=""),
    telemetry_summary: str = Form(default=""),
    baseline_reference: str = Form(default=""),
    user: CurrentUser | None = Depends(require_role("analyst")),
    _rate_limit = Depends(require_rate_limit("analysis")),
):
    """Create a persisted analysis job and return resource URLs."""
    uploads = await _collect_uploads(image, images)

    norad = norad_id.strip() or None
    if norad and not re.fullmatch(r"\d{1,9}", norad):
        raise HTTPException(status_code=400, detail="norad_id must be 1-9 digits")
    normalized_asset_type = _normalize_asset_type(asset_type)
    parsed_capture_metadata = _safe_json_form(capture_metadata, "capture_metadata")
    parsed_telemetry_summary = _safe_json_form(telemetry_summary, "telemetry_summary")
    parsed_baseline_reference = _safe_json_form(baseline_reference, "baseline_reference")
    assessment_contract = _assessment_contract_or_400(
        assessment_mode=assessment_mode,
        capture_metadata=parsed_capture_metadata,
        telemetry_summary=parsed_telemetry_summary,
        baseline_reference=parsed_baseline_reference,
    )

    created = await _create_analysis_record(
        uploads=uploads,
        norad=norad,
        context=context,
        asset_type=normalized_asset_type,
        asset_name=asset_name,
        external_asset_id=external_asset_id,
        inspection_epoch=inspection_epoch.strip(),
        target_subsystem=target_subsystem.strip(),
        capture_metadata=parsed_capture_metadata,
        telemetry_summary=parsed_telemetry_summary,
        baseline_reference=parsed_baseline_reference,
        assessment_mode=assessment_contract["assessment_mode"],
        user=user,
        request_id=getattr(request.state, "request_id", None),
    )
    analysis_id = created["analysis_id"] if isinstance(created, dict) else str(created)
    dispatch = (
        await _dispatch_analysis(
            analysis_id=analysis_id,
        )
        if isinstance(created, dict)
        else {"dispatch_mode": "inline", "queue_job_id": None}
    )
    record_analysis_created(normalized_asset_type)

    return {
        "analysis_id": analysis_id,
        "status": "dispatched" if dispatch["dispatch_mode"] == "arq" else "queued",
        "analysis_url": f"/api/v1/analyses/{analysis_id}",
        "events_url": f"/api/v1/analyses/{analysis_id}/events/stream",
        "assessment_mode": created.get("assessment_mode", assessment_contract["assessment_mode"]) if isinstance(created, dict) else assessment_contract["assessment_mode"],
        "decision_authority": created.get("decision_authority", assessment_contract["decision_authority"]) if isinstance(created, dict) else assessment_contract["decision_authority"],
        "request_id": getattr(request.state, "request_id", None),
        "dispatch_mode": dispatch["dispatch_mode"],
        "queue_job_id": dispatch["queue_job_id"],
    }


# ── Legacy analyze stream wrapper ───────────────────────────────────
@app.post("/api/v1/analyze")
async def analyze(
    image: UploadFile = File(...),
    norad_id: str = Form(default=""),
    context: str = Form(default=""),
    asset_type: str = Form(default="satellite"),
    asset_name: str = Form(default=""),
    external_asset_id: str = Form(default=""),
    inspection_epoch: str = Form(default=""),
    target_subsystem: str = Form(default=""),
    assessment_mode: str = Form(default="PUBLIC_SCREEN"),
    capture_metadata: str = Form(default=""),
    telemetry_summary: str = Form(default=""),
    baseline_reference: str = Form(default=""),
    user: CurrentUser | None = Depends(require_role("analyst")),
):
    """
    Legacy wrapper: preserve inline SSE behavior for one transition window.
    """
    if not settings.DEMO_MODE:
        raise HTTPException(
            status_code=410,
            detail="Legacy /api/analyze is retired for production use. Submit work via POST /api/analyses instead.",
            headers=_legacy_analyze_headers(),
        )

    uploads = await _collect_uploads(image, None)
    _safe_json_form(capture_metadata, "capture_metadata")
    _safe_json_form(telemetry_summary, "telemetry_summary")
    _safe_json_form(baseline_reference, "baseline_reference")
    try:
        normalize_assessment_mode(assessment_mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _normalize_asset_type(asset_type)
    asset_name.strip()
    external_asset_id.strip()
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

    return EventSourceResponse(event_generator(), headers=_legacy_analyze_headers())


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


@app.get("/api/v1/demos")
async def list_demos():
    """List available demo cases."""
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=404, detail="Demo catalog unavailable outside demo mode")
    return {"demos": DEMO_CONFIGS}


@app.post("/api/v1/demo/{demo_name}")
async def run_demo(demo_name: str):
    """Run a pre-configured demo analysis."""
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=404, detail="Demo execution unavailable outside demo mode")
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
@app.get("/api/v1/analyses")
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
                        "asset_id": getattr(a, "asset_id", None),
                        "asset_name": getattr(getattr(a, "asset", None), "name", None),
                        "asset_external_id": getattr(getattr(a, "asset", None), "external_asset_id", None),
                        "asset_identity_source": getattr(getattr(a, "asset", None), "identity_source", None),
                        "subsystem_id": getattr(a, "subsystem_id", None),
                        "subsystem_key": getattr(getattr(a, "subsystem", None), "subsystem_key", None),
                        "status": a.status,
                        "asset_type": getattr(a, "asset_type", "satellite"),
                        "request_id": getattr(a, "request_id", None),
                        "inspection_epoch": getattr(a, "inspection_epoch", None),
                        "target_subsystem": getattr(a, "target_subsystem", None),
                        "queue_job_id": getattr(a, "queue_job_id", None),
                        "dispatch_mode": getattr(a, "dispatch_mode", None),
                        "retry_count": getattr(a, "retry_count", 0),
                        "human_review_required": getattr(a, "human_review_required", True),
                        "decision_blocked_reason": getattr(a, "decision_blocked_reason", None),
                        "decision_status": getattr(a, "decision_status", "pending_policy"),
                        "decision_summary": getattr(a, "decision_summary", {}) or {},
                        "decision_recommended_action": getattr(a, "decision_recommended_action", None),
                        "decision_confidence": getattr(a, "decision_confidence", None),
                        "decision_urgency": getattr(a, "decision_urgency", None),
                        "triage_score": getattr(a, "triage_score", None),
                        "triage_band": getattr(a, "triage_band", None),
                        "triage_factors": getattr(a, "triage_factors", {}) or {},
                        "recurrence_count": getattr(a, "recurrence_count", 0),
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


@app.get("/api/v1/analyses/{analysis_id}")
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
                "asset_id": getattr(analysis, "asset_id", None),
                "asset_name": getattr(getattr(analysis, "asset", None), "name", None),
                "asset_external_id": getattr(getattr(analysis, "asset", None), "external_asset_id", None),
                "asset_identity_source": getattr(getattr(analysis, "asset", None), "identity_source", None),
                "subsystem_id": getattr(analysis, "subsystem_id", None),
                "subsystem_key": getattr(getattr(analysis, "subsystem", None), "subsystem_key", None),
                "status": analysis.status,
                "asset_type": getattr(analysis, "asset_type", "satellite"),
                "request_id": getattr(analysis, "request_id", None),
                "inspection_epoch": getattr(analysis, "inspection_epoch", None),
                "target_subsystem": getattr(analysis, "target_subsystem", None),
                "assessment_mode": (getattr(analysis, "capture_metadata", {}) or {}).get("assessment_mode", "PUBLIC_SCREEN"),
                "decision_authority": (
                    ((getattr(analysis, "insurance_risk_result", {}) or {}).get("decision_authority"))
                    or ((getattr(analysis, "evidence_bundle_summary", {}) or {}).get("assessment_contract", {}) or {}).get("decision_authority")
                    or "SCREENING_ONLY"
                ),
                "required_evidence_gaps": (
                    ((getattr(analysis, "insurance_risk_result", {}) or {}).get("required_evidence_gaps"))
                    or ((getattr(analysis, "evidence_bundle_summary", {}) or {}).get("assessment_contract", {}) or {}).get("required_evidence_gaps")
                    or []
                ),
                "unsupported_claims_blocked": (
                    ((getattr(analysis, "insurance_risk_result", {}) or {}).get("unsupported_claims_blocked"))
                    or ((getattr(analysis, "evidence_bundle_summary", {}) or {}).get("assessment_contract", {}) or {}).get("unsupported_claims_blocked")
                    or []
                ),
                "queue_job_id": getattr(analysis, "queue_job_id", None),
                "dispatch_mode": getattr(analysis, "dispatch_mode", None),
                "retry_count": getattr(analysis, "retry_count", 0),
                "max_retries": getattr(analysis, "max_retries", 0),
                "last_error": getattr(analysis, "last_error", None),
                "governance_policy_version": getattr(analysis, "governance_policy_version", None),
                "model_manifest": getattr(analysis, "model_manifest", {}) or {},
                "human_review_required": getattr(analysis, "human_review_required", True),
                "decision_blocked_reason": getattr(analysis, "decision_blocked_reason", None),
                "decision_summary": getattr(analysis, "decision_summary", {}) or {},
                "decision_status": getattr(analysis, "decision_status", "pending_policy"),
                "decision_recommended_action": getattr(analysis, "decision_recommended_action", None),
                "decision_confidence": getattr(analysis, "decision_confidence", None),
                "decision_urgency": getattr(analysis, "decision_urgency", None),
                "decision_approved_by": getattr(analysis, "decision_approved_by", None),
                "decision_approved_at": (
                    getattr(analysis, "decision_approved_at", None).isoformat()
                    if getattr(analysis, "decision_approved_at", None)
                    else None
                ),
                "decision_override_reason": getattr(analysis, "decision_override_reason", None),
                "decision_last_evaluated_at": (
                    getattr(analysis, "decision_last_evaluated_at", None).isoformat()
                    if getattr(analysis, "decision_last_evaluated_at", None)
                    else None
                ),
                "triage_score": getattr(analysis, "triage_score", None),
                "triage_band": getattr(analysis, "triage_band", None),
                "triage_factors": getattr(analysis, "triage_factors", {}) or {},
                "recurrence_count": getattr(analysis, "recurrence_count", 0),
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
                "permissions": {
                    "can_review_decision": (not settings.AUTH_ENABLED) or bool(user and user.role in {"analyst", "admin"}),
                    "can_override_decision": (not settings.AUTH_ENABLED) or bool(user and user.role == "admin"),
                },
                "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
                "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
            }
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@app.get("/api/v1/ops/dead-letters")
async def list_dead_letters(
    limit: int = 50,
    user: CurrentUser | None = Depends(require_role("admin")),
):
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            items = await repo.list_dead_letters(org_id=user.org_id if user else None, limit=limit)
            return {
                "items": [
                    {
                        "id": item.id,
                        "analysis_id": item.analysis_id,
                        "job_id": item.job_id,
                        "queue_name": item.queue_name,
                        "attempts": item.attempts,
                        "error_message": item.error_message,
                        "created_at": item.created_at.isoformat() if item.created_at else None,
                    }
                    for item in items
                ]
            }
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@app.get("/api/v1/analyses/{analysis_id}/events/stream")
async def stream_analysis_events(
    analysis_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Stream persisted analysis events via SSE."""
    return EventSourceResponse(_stream_analysis_events_generator(analysis_id, user))


@app.get("/api/v1/analyses/{analysis_id}/events")
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
if settings.STORAGE_BACKEND == "local":
    settings.storage_local_root_path.mkdir(parents=True, exist_ok=True)
