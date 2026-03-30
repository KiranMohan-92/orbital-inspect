"""
Orbital Environment Agent — assesses space environment hazards at the satellite's orbit.

Combines NASA ORDEM debris flux tables, NOAA SWPC space weather data,
and radiation/thermal models to quantify environmental stressors.
"""

import logging
from pathlib import Path
from services.gemini_service import (
    is_adk_available,
    run_adk_agent,
    get_model_name,
    parse_json_response,
)
from services.ordem_service import format_flux_summary, lookup_radiation, lookup_thermal
from services.space_weather_service import fetch_space_weather, format_weather_summary
from models.satellite import OrbitalEnvironmentAnalysis

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "orbital_environment_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text()


def _build_agent():
    if not is_adk_available():
        return None

    from google.adk.agents import Agent
    from google.adk.tools import google_search

    return Agent(
        name="orbital_environment_agent",
        model=get_model_name(),
        instruction=_PROMPT_TEMPLATE,
        tools=[google_search],
        output_key="environment_output",
    )


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


async def analyze_orbital_environment(
    altitude_km: float | None = None,
    inclination_deg: float | None = None,
    orbital_regime: str = "UNKNOWN",
    satellite_context: str = "",
) -> OrbitalEnvironmentAnalysis:
    """
    Assess the orbital environment hazards for a satellite.

    Enriches the AI analysis with real data from ORDEM tables and NOAA SWPC.

    Args:
        altitude_km: Orbital altitude in kilometers
        inclination_deg: Orbital inclination in degrees
        orbital_regime: LEO/MEO/GEO/HEO/SSO
        satellite_context: Context from classification agent

    Returns:
        OrbitalEnvironmentAnalysis with quantified environmental stressors
    """
    # Gather real data to provide as context
    enrichment_parts: list[str] = []

    # ORDEM debris data
    if altitude_km is not None:
        debris_summary = format_flux_summary(altitude_km)
        enrichment_parts.append(debris_summary)

    # Radiation environment
    if altitude_km is not None:
        rad_data = lookup_radiation(altitude_km)
        if rad_data:
            enrichment_parts.append(
                f"Radiation Environment (AE-8/AP-8 Model):\n"
                f"  Altitude range: {rad_data.get('altitude_range', 'N/A')}\n"
                f"  Trapped proton flux: {rad_data.get('trapped_proton_flux', 0):.2e} p/cm²/s\n"
                f"  Trapped electron flux: {rad_data.get('trapped_electron_flux', 0):.2e} e/cm²/s\n"
                f"  Annual dose: {rad_data.get('annual_dose_krad', 0):.1f} krad(Si)/year\n"
                f"  SEE rate: {rad_data.get('see_rate_per_day', 0):.3f} events/day"
            )

    # Thermal cycling
    regime_key = orbital_regime if orbital_regime != "UNKNOWN" else "LEO"
    thermal_data = lookup_thermal(regime_key)
    if thermal_data:
        enrichment_parts.append(
            f"Thermal Cycling ({regime_key}):\n"
            f"  Temperature range: {thermal_data['min_temp_c']}°C to {thermal_data['max_temp_c']}°C\n"
            f"  Cycles per day: {thermal_data['cycles_per_day']}\n"
            f"  Eclipses per orbit: {thermal_data['eclipses_per_orbit']}"
        )

    # Real-time space weather from NOAA SWPC
    try:
        weather = await fetch_space_weather()
        enrichment_parts.append(format_weather_summary(weather))
    except Exception as e:
        log.warning("Space weather fetch failed", exc_info=True)
        enrichment_parts.append("Space weather: data unavailable (NOAA SWPC unreachable)")

    # Build prompt with all enrichment data
    enrichment_text = "\n\n".join(enrichment_parts) if enrichment_parts else "No orbital data available."
    prompt = (
        f"Assess the orbital environment for this satellite.\n\n"
        f"Orbital parameters:\n"
        f"  Regime: {orbital_regime}\n"
        f"  Altitude: {altitude_km or 'unknown'} km\n"
        f"  Inclination: {inclination_deg or 'unknown'}°\n\n"
        f"Real data from ORDEM + SWPC:\n{enrichment_text}"
    )
    if satellite_context:
        prompt += f"\n\nSatellite context:\n{satellite_context}"

    agent = _get_agent()

    try:
        data = await run_adk_agent(
            agent, prompt
        ) if agent else await _fallback(prompt)
        return OrbitalEnvironmentAnalysis(**data)
    except Exception as e:
        log.error("Environment analysis failed", exc_info=True)
        return OrbitalEnvironmentAnalysis(
            orbital_regime=orbital_regime,
            altitude_km=altitude_km,
            inclination_deg=inclination_deg,
            data_sources=["Error: analysis failed"],
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
