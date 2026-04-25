"""
Satellite Vision Agent — detects damage on satellite components from imagery.

Space-specific damage taxonomy including micrometeorite craters, solar cell
degradation, thermal blanket damage, deployment anomalies, and debris strikes.
Returns bounding boxes with confidence scores and power impact estimates.
"""

import logging
from pathlib import Path
from services.gemini_service import (
    is_adk_available,
    run_adk_agent,
    get_model_name,
    parse_json_response,
)
from models.satellite import SatelliteDamagesAssessment
from services.assessment_mode_service import build_assessment_contract, enforce_vision_claim_boundary

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "satellite_vision_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text()


def _build_agent():
    if not is_adk_available():
        return None

    from google.adk.agents import Agent

    return Agent(
        name="satellite_vision_agent",
        model=get_model_name(),
        instruction=_PROMPT_TEMPLATE,
        output_key="vision_output",
    )


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


async def analyze_satellite_image(
    image_bytes: bytes,
    image_mime: str = "image/jpeg",
    component_hint: str = "",
    satellite_context: str = "",
    assessment_mode: str = "PUBLIC_SCREEN",
    assessment_contract: dict | None = None,
) -> SatelliteDamagesAssessment:
    """
    Analyze a satellite image for structural damage.

    Args:
        image_bytes: Satellite/component image data
        image_mime: Image MIME type
        component_hint: Optional hint about which component (solar_array, antenna, bus)
        satellite_context: Optional context from classification agent

    Returns:
        SatelliteDamagesAssessment with damages, bounding boxes, and power impact
    """
    prompt = "Analyze this satellite image for structural damage and degradation."
    if component_hint:
        prompt += f" Focus on the {component_hint} component."
    if satellite_context:
        prompt += f"\n\nSatellite context: {satellite_context}"
    if assessment_mode == "PUBLIC_SCREEN":
        prompt += (
            "\n\nAssessment mode: PUBLIC_SCREEN. Do not estimate millimeter-scale dimensions, "
            "power loss, or functional impact unless calibrated range/camera/scale metadata is provided. "
            "When metadata is missing, provide qualitative observations and evidence gaps only."
        )

    agent = _get_agent()

    try:
        data = await run_adk_agent(
            agent,
            prompt,
            image_bytes=image_bytes,
            image_mime=image_mime,
        ) if agent else await _fallback(prompt, image_bytes, image_mime)
        if "error" in data and "raw_text" in data:
            raise ValueError("Agent response could not be parsed")
        assessment = SatelliteDamagesAssessment(**data)
        return enforce_vision_claim_boundary(
            assessment,
            assessment_contract
            or build_assessment_contract(
                assessment_mode=assessment_mode,
                capture_metadata={},
                telemetry_summary={},
                baseline_reference={},
            ),
        )
    except Exception as e:
        log.error("Vision analysis failed", exc_info=True)
        return SatelliteDamagesAssessment(
            overall_pattern="Vision analysis failed",
            overall_severity="MODERATE",
            overall_confidence=0.0,
            degraded=True,
        )


async def _fallback(prompt: str, image_bytes: bytes, image_mime: str) -> dict:
    from services.gemini_service import client, get_model_name
    from google.genai import types
    import asyncio

    def _sync():
        return client.models.generate_content(
            model=get_model_name(),
            contents=types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=_PROMPT_TEMPLATE + "\n\n" + prompt),
                    types.Part.from_bytes(data=image_bytes, mime_type=image_mime),
                ],
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, _sync)
    return parse_json_response(response.text or "{}")
