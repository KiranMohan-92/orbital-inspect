"""
Satellite Failure Mode Agent — identifies failure mechanisms and historical precedents.

Combines visual damage data + environmental stressors to determine the most likely
failure mode, its progression rate, and relevant insurance claim precedents.
Uses Google Search grounding for up-to-date satellite incident data.
"""

import logging
from pathlib import Path
from services.gemini_service import (
    is_adk_available,
    run_adk_agent,
    get_model_name,
    parse_json_response,
)
from models.satellite import SatelliteFailureModeAnalysis

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "satellite_failure_mode_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text()


def _build_agent():
    if not is_adk_available():
        return None

    from google.adk.agents import Agent
    from google.adk.tools import google_search

    return Agent(
        name="satellite_failure_mode_agent",
        model=get_model_name(),
        instruction=_PROMPT_TEMPLATE,
        tools=[google_search],
        output_key="failure_mode_output",
    )


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


async def analyze_failure_modes(
    classification_context: str = "",
    vision_context: str = "",
    environment_context: str = "",
) -> SatelliteFailureModeAnalysis:
    """
    Analyze satellite failure modes based on accumulated pipeline data.

    Args:
        classification_context: JSON string from Classification Agent output
        vision_context: JSON string from Vision Agent output
        environment_context: JSON string from Environment Agent output

    Returns:
        SatelliteFailureModeAnalysis with failure mode, mechanism, precedents
    """
    prompt = (
        "Analyze the failure modes for this satellite based on the following assessment data.\n\n"
        f"=== SATELLITE CLASSIFICATION ===\n{classification_context}\n\n"
        f"=== VISUAL DAMAGE ASSESSMENT ===\n{vision_context}\n\n"
        f"=== ORBITAL ENVIRONMENT ===\n{environment_context}"
    )

    agent = _get_agent()

    try:
        data = await run_adk_agent(
            agent, prompt
        ) if agent else await _fallback(prompt)
        if "error" in data and "raw_text" in data:
            raise ValueError("Agent response could not be parsed")
        return SatelliteFailureModeAnalysis(**data)
    except Exception as e:
        log.error("Failure mode analysis failed", exc_info=True)
        return SatelliteFailureModeAnalysis(
            failure_mode="Analysis failed",
            mechanism=str(e),
            progression_rate="MODERATE",
            degraded=True,
        )


async def _fallback(prompt: str) -> dict:
    from services.gemini_service import client, get_model_name as gmn
    from google.genai import types
    import asyncio

    def _sync():
        return client.models.generate_content(
            model=gmn(),
            contents=types.Content(
                role="user",
                parts=[types.Part.from_text(text=_PROMPT_TEMPLATE + "\n\n" + prompt)],
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, _sync)
    return parse_json_response(response.text or "{}")
