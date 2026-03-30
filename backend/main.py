"""
Orbital Inspect — FastAPI backend with SSE streaming.

Endpoints:
  POST /api/analyze      — Upload satellite image + optional NORAD ID, stream SSE events
  GET  /api/health       — Health check
  GET  /api/demo/{name}  — Run pre-cached demo analysis
"""

import json
import re
import logging
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from config import settings
from agents.orchestrator import run_satellite_pipeline
from services.sse_service import format_sse_error

log = logging.getLogger(__name__)

app = FastAPI(
    title="Orbital Inspect",
    description="Satellite Condition Intelligence — AI-powered damage assessment for space insurers",
    version="0.1.0",
)

ALLOWED_ORIGINS = getattr(settings, "ALLOWED_ORIGINS", None) or [
    "http://localhost:5173", "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Demo cache directory ─────────────────────────────────────────────
DEMO_DIR = Path(__file__).parent / "data" / "demo_cache"


# ── Health ───────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    from services.gemini_service import is_adk_available
    return {
        "status": "ok",
        "service": "orbital-inspect",
        "adk_available": is_adk_available(),
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

    The response is a Server-Sent Event stream with events for each agent
    stage: orbital_classification → satellite_vision → orbital_environment →
    failure_mode → insurance_risk.
    """
    # Validate file type
    content_type = image.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Read image bytes (limit to 20MB)
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


# ── Demo endpoint ────────────────────────────────────────────────────
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
    """
    Run a pre-configured demo analysis.

    If a cached result exists, stream it immediately. Otherwise, run the full
    pipeline using the demo image.
    """
    if demo_name not in DEMO_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Demo '{demo_name}' not found")

    config = DEMO_CONFIGS[demo_name]

    # Check for cached result
    cache_path = DEMO_DIR / f"{demo_name}.json"
    if cache_path.exists():
        cached_events = json.loads(cache_path.read_text())

        async def cached_generator():
            import asyncio
            for event in cached_events:
                yield event
                await asyncio.sleep(0.3)  # Simulate processing time

        return EventSourceResponse(cached_generator())

    # Check for demo image
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


# ── Ensure data directories exist ────────────────────────────────────
(Path(__file__).parent / "data" / "demo_images").mkdir(parents=True, exist_ok=True)
(Path(__file__).parent / "data" / "demo_cache").mkdir(parents=True, exist_ok=True)
