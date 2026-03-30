"""
Orchestrator — 5-stage satellite inspection pipeline with SSE streaming.

Runs agents sequentially, streaming SSE events between stages:
  1. Orbital Classification → identify satellite
  2. Satellite Vision → detect damage
  3. Orbital Environment → assess hazards
  4. Failure Mode → determine mechanism + precedents
  5. Insurance Risk → actuarial-grade risk score

Each agent's output feeds into the next, building a complete
Satellite Condition Report.
"""

import json
import logging
import uuid
from typing import AsyncGenerator

from models.events import AgentEvent
from services.resilience import resilient_call, gemini_breaker, CircuitBreakerOpen
from services.sse_service import format_sse_event, format_sse_done, format_sse_error
from config import settings

log = logging.getLogger(__name__)

AGENT_ORDER = [
    "orbital_classification",
    "satellite_vision",
    "orbital_environment",
    "failure_mode",
    "insurance_risk",
]


def _safe_error(agent: str, exc: Exception) -> str:
    """Log full exception server-side, return safe message for client."""
    err_id = uuid.uuid4().hex[:8]
    log.error("[%s] failed err_id=%s", agent, err_id, exc_info=True)
    return f"Analysis failed (ref: {err_id})"


async def run_satellite_pipeline(
    image_bytes: bytes,
    image_mime: str = "image/jpeg",
    norad_id: str | None = None,
    additional_context: str = "",
) -> AsyncGenerator[dict, None]:
    """
    Execute the full 5-agent satellite inspection pipeline.

    Yields SSE-formatted events for each agent stage. The frontend
    consumes these via EventSource to show real-time progress.
    """
    # Queue all agents
    for agent_name in AGENT_ORDER:
        yield format_sse_event(AgentEvent.queued(agent_name))

    evidence_gaps: list[str] = []

    # ── Stage 1: Orbital Classification ──────────────────────────────
    yield format_sse_event(AgentEvent.thinking(
        "orbital_classification", "Identifying satellite type, bus platform, and orbital regime..."
    ))

    try:
        from agents.orbital_classification_agent import classify_satellite
        classification = await resilient_call(
            lambda: classify_satellite(
                image_bytes=image_bytes,
                image_mime=image_mime,
                norad_id=norad_id,
                additional_context=additional_context,
            ),
            timeout_seconds=settings.AGENT_TIMEOUT_SECONDS,
            max_retries=2,
            circuit_breaker=gemini_breaker,
        )
        classification_dict = classification.model_dump()
        yield format_sse_event(AgentEvent.complete("orbital_classification", classification_dict))
    except CircuitBreakerOpen:
        msg = _safe_error("orbital_classification", Exception("Service temporarily unavailable"))
        yield format_sse_event(AgentEvent.error("orbital_classification", msg))
        yield format_sse_error("Gemini API circuit breaker is open — service recovering")
        return
    except Exception as e:
        msg = _safe_error("orbital_classification", e)
        yield format_sse_event(AgentEvent.error("orbital_classification", msg))
        yield format_sse_error("Pipeline failed at satellite classification")
        return

    # Fail-closed: reject non-satellite imagery
    if not classification.valid:
        yield format_sse_event(AgentEvent.error(
            "orbital_classification",
            classification.rejection_reason or "Image rejected: not a satellite"
        ))
        yield format_sse_error(classification.rejection_reason or "Image rejected")
        return

    # Build satellite context for downstream agents
    sat_context = (
        f"Satellite: {classification.satellite_type}, Bus: {classification.bus_platform or 'unknown'}, "
        f"Regime: {classification.orbital_regime}, Design life: {classification.design_life_years or 'unknown'} years, "
        f"Age: {classification.estimated_age_years or 'unknown'} years, "
        f"Components: {', '.join(classification.expected_components)}"
    )

    # ── Stage 2: Satellite Vision ────────────────────────────────────
    yield format_sse_event(AgentEvent.thinking(
        "satellite_vision", "Scanning for micrometeorite impacts, solar cell degradation, thermal damage..."
    ))

    try:
        from agents.satellite_vision_agent import analyze_satellite_image
        vision = await resilient_call(
            lambda: analyze_satellite_image(
                image_bytes=image_bytes,
                image_mime=image_mime,
                satellite_context=sat_context,
            ),
            timeout_seconds=settings.AGENT_TIMEOUT_SECONDS,
            max_retries=2,
            circuit_breaker=gemini_breaker,
        )
        vision_dict = vision.model_dump()
        yield format_sse_event(AgentEvent.complete("satellite_vision", vision_dict))
    except Exception as e:
        msg = _safe_error("satellite_vision", e)
        yield format_sse_event(AgentEvent.error("satellite_vision", msg))
        vision = None
        vision_dict = {}
        evidence_gaps.append("satellite_vision")

    # ── Stage 3: Orbital Environment ─────────────────────────────────
    yield format_sse_event(AgentEvent.thinking(
        "orbital_environment", "Querying NASA ORDEM debris flux and NOAA space weather..."
    ))

    # Extract orbital parameters from classification
    altitude_km = None
    inclination_deg = None

    # Try to get altitude from CelesTrak data if NORAD ID was provided
    if norad_id:
        try:
            from services.celestrak_service import lookup_by_norad_id
            celestrak_data = await lookup_by_norad_id(norad_id)
            if celestrak_data:
                altitude_km = celestrak_data.get("altitude_avg_km")
                inclination_deg = celestrak_data.get("inclination_deg")
        except Exception:
            log.warning("[orchestrator] CelesTrak lookup failed for NORAD %s", norad_id, exc_info=True)

    try:
        from agents.orbital_environment_agent import analyze_orbital_environment
        environment = await resilient_call(
            lambda: analyze_orbital_environment(
                altitude_km=altitude_km,
                inclination_deg=inclination_deg,
                orbital_regime=classification.orbital_regime,
                satellite_context=sat_context,
            ),
            timeout_seconds=settings.AGENT_TIMEOUT_SECONDS,
            max_retries=2,
            circuit_breaker=gemini_breaker,
        )
        environment_dict = environment.model_dump()
        yield format_sse_event(AgentEvent.complete("orbital_environment", environment_dict))
    except Exception as e:
        msg = _safe_error("orbital_environment", e)
        yield format_sse_event(AgentEvent.error("orbital_environment", msg))
        environment = None
        environment_dict = {}
        evidence_gaps.append("orbital_environment")

    # ── Stage 4: Failure Mode Analysis ───────────────────────────────
    yield format_sse_event(AgentEvent.thinking(
        "failure_mode", "Analyzing failure mechanisms and matching historical precedents..."
    ))

    try:
        from agents.satellite_failure_mode_agent import analyze_failure_modes
        failure_mode = await resilient_call(
            lambda: analyze_failure_modes(
                classification_context=json.dumps(classification_dict, default=str),
                vision_context=json.dumps(vision_dict, default=str),
                environment_context=json.dumps(environment_dict, default=str),
            ),
            timeout_seconds=settings.AGENT_TIMEOUT_SECONDS,
            max_retries=2,
            circuit_breaker=gemini_breaker,
        )
        failure_mode_dict = failure_mode.model_dump()
        yield format_sse_event(AgentEvent.complete("failure_mode", failure_mode_dict))
    except Exception as e:
        msg = _safe_error("failure_mode", e)
        yield format_sse_event(AgentEvent.error("failure_mode", msg))
        failure_mode = None
        failure_mode_dict = {}
        evidence_gaps.append("failure_mode")

    # ── Stage 5: Insurance Risk Assessment ───────────────────────────
    yield format_sse_event(AgentEvent.thinking(
        "insurance_risk", "Computing risk matrix, financial exposure, and underwriting recommendation..."
    ))

    # Build evidence gap context for insurance risk agent
    evidence_gap_context = ""
    if evidence_gaps:
        evidence_gap_context = (
            f"\n\nWARNING — INCOMPLETE EVIDENCE: The following pipeline stages failed and "
            f"their data is missing from this assessment: {', '.join(evidence_gaps)}. "
            f"You must account for this missing evidence in your risk assessment and recommendation."
        )

    try:
        from agents.insurance_risk_agent import assess_insurance_risk
        insurance_risk = await resilient_call(
            lambda: assess_insurance_risk(
                classification_context=json.dumps(classification_dict, default=str),
                vision_context=json.dumps(vision_dict, default=str),
                environment_context=json.dumps(environment_dict, default=str),
                failure_mode_context=json.dumps(failure_mode_dict, default=str) + evidence_gap_context,
            ),
            timeout_seconds=settings.AGENT_TIMEOUT_SECONDS,
            max_retries=2,
            circuit_breaker=gemini_breaker,
        )
        insurance_risk_dict = insurance_risk.model_dump()

        # Force partial report metadata when evidence is missing
        if evidence_gaps:
            insurance_risk_dict["evidence_gaps"] = evidence_gaps
            insurance_risk_dict["report_completeness"] = "PARTIAL"
            if insurance_risk_dict.get("underwriting_recommendation") not in ("FURTHER_INVESTIGATION", "UNINSURABLE"):
                insurance_risk_dict["underwriting_recommendation"] = "FURTHER_INVESTIGATION"
                insurance_risk_dict["recommendation_rationale"] = (
                    f"Incomplete evidence: {', '.join(evidence_gaps)} failed. "
                    + insurance_risk_dict.get("recommendation_rationale", "")
                )

        yield format_sse_event(AgentEvent.complete("insurance_risk", insurance_risk_dict))
    except Exception as e:
        msg = _safe_error("insurance_risk", e)
        yield format_sse_event(AgentEvent.error("insurance_risk", msg))

    # ── Pipeline Complete ────────────────────────────────────────────
    yield format_sse_done()
