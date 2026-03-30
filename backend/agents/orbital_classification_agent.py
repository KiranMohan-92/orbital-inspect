"""
Orbital Classification Agent — identifies and classifies satellites from imagery.

Uses CelesTrak API for orbital parameter enrichment when NORAD ID is provided.
Classifies satellite type, bus platform, orbital regime, and expected components.
"""

import logging
from pathlib import Path

log = logging.getLogger(__name__)
from services.gemini_service import (
    is_adk_available,
    run_adk_agent,
    get_model_name,
    parse_json_response,
)
from models.satellite import ClassificationResult

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "orbital_classification_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text()


def _build_agent():
    if not is_adk_available():
        return None

    from google.adk.agents import Agent

    return Agent(
        name="orbital_classification_agent",
        model=get_model_name(),
        instruction=_PROMPT_TEMPLATE,
        output_key="classification_output",
    )


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


async def classify_satellite(
    image_bytes: bytes,
    image_mime: str = "image/jpeg",
    norad_id: str | None = None,
    additional_context: str = "",
) -> ClassificationResult:
    """
    Classify a satellite from its image, optionally enriched with CelesTrak data.

    Args:
        image_bytes: Satellite image data
        image_mime: Image MIME type
        norad_id: Optional NORAD catalog number for orbital data enrichment
        additional_context: Optional user-provided context

    Returns:
        ClassificationResult with satellite type, regime, components, design life
    """
    # Enrich with CelesTrak data if NORAD ID provided
    celestrak_context = ""
    if norad_id:
        try:
            from services.celestrak_service import lookup_by_norad_id
            sat_data = await lookup_by_norad_id(norad_id)
            if sat_data:
                celestrak_context = (
                    f"\n\nCelesTrak orbital data for NORAD {norad_id}:\n"
                    f"  Name: {sat_data['name']}\n"
                    f"  COSPAR ID: {sat_data['cospar_id']}\n"
                    f"  Orbital regime: {sat_data['orbital_regime']}\n"
                    f"  Altitude: {sat_data['altitude_avg_km']} km\n"
                    f"  Inclination: {sat_data['inclination_deg']}°\n"
                    f"  Launch date: {sat_data['launch_date']}\n"
                    f"  Country: {sat_data['country_code']}\n"
                    f"  RCS size: {sat_data['rcs_size']}"
                )
        except Exception as e:
            log.warning("CelesTrak lookup failed", exc_info=True)

    prompt = f"Classify this satellite image.{celestrak_context}"
    if additional_context:
        prompt += f"\n\nUser context: {additional_context}"

    agent = _get_agent()

    try:
        data = await run_adk_agent(
            agent,
            prompt,
            image_bytes=image_bytes,
            image_mime=image_mime,
        ) if agent else await _fallback(prompt, image_bytes, image_mime)

        # Fail-closed: reject unparseable agent responses
        if "error" in data and "raw_text" in data:
            log.warning("Classification returned unparseable response")
            return ClassificationResult(
                valid=False,
                rejection_reason="Agent response could not be parsed",
                degraded=True,
            )

        return ClassificationResult(**data)
    except Exception as e:
        log.error("Classification failed", exc_info=True)
        return ClassificationResult(
            valid=False,
            rejection_reason="Classification unavailable: agent error",
            satellite_type="other",
            orbital_regime="UNKNOWN",
            notes=f"Classification failed: {e}",
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
