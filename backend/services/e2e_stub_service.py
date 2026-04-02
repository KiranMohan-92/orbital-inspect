"""
Deterministic full-stack pipeline scenarios for browser E2E.

Enabled only when settings.E2E_TEST_MODE is true. This allows Playwright to
exercise the real frontend, API submission flow, worker persistence, SSE
streaming, and portfolio/report surfaces without depending on external Gemini
or orbital data services.
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from models.events import AgentEvent
from services.sse_service import format_sse_done, format_sse_error, format_sse_event


AGENT_ORDER = [
    "orbital_classification",
    "satellite_vision",
    "orbital_environment",
    "failure_mode",
    "insurance_risk",
]

THINKING_MESSAGES = {
    "orbital_classification": "Identifying satellite type, bus platform, and orbital regime...",
    "satellite_vision": "Scanning for micrometeorite impacts, solar cell degradation, thermal damage...",
    "orbital_environment": "Querying NASA ORDEM debris flux and NOAA space weather...",
    "failure_mode": "Analyzing failure mechanisms and matching historical precedents...",
    "insurance_risk": "Computing risk matrix, financial exposure, and underwriting recommendation...",
}


def _scenario_key(additional_context: str) -> str:
    context = additional_context.lower()
    for key in ("partial", "rejected", "failed", "success"):
        if f"[e2e:{key}]" in context:
            return key
    return "success"


def _wrap_event(event: AgentEvent, analysis_id: str, sequence: int) -> dict:
    event.analysis_id = analysis_id
    event.sequence = sequence
    return format_sse_event(event)


def _classification_payload(norad_id: str | None, *, valid: bool = True) -> dict:
    if not valid:
        return {
            "valid": False,
            "rejection_reason": "Imagery rejected: target does not appear to be a supported orbital asset.",
            "satellite_type": "other",
            "bus_platform": None,
            "orbital_regime": "UNKNOWN",
            "expected_components": [],
            "design_life_years": None,
            "estimated_age_years": None,
            "operator": None,
            "notes": "Deterministic rejection scenario for browser E2E.",
            "degraded": False,
        }

    return {
        "valid": True,
        "rejection_reason": None,
        "satellite_type": "technology_demo",
        "bus_platform": "OrbitalNode-A",
        "orbital_regime": "LEO",
        "expected_components": ["solar_array", "bus", "radiator"],
        "design_life_years": 8.0,
        "estimated_age_years": 2.0,
        "operator": "Orbital Compute Consortium",
        "notes": f"Deterministic E2E classification for NORAD {norad_id or 'unknown'}.",
        "degraded": False,
    }


def _vision_payload(*, degraded: bool = False) -> dict:
    return {
        "damages": [
            {
                "id": 1,
                "type": "surface_anomaly",
                "description": "Localized panel discoloration detected in deterministic E2E scenario.",
                "bounding_box": [96, 144, 164, 212],
                "label": "Surface anomaly",
                "severity": "MINOR",
                "confidence": 0.88,
                "uncertain": degraded,
                "estimated_power_impact_pct": 0.8,
            }
        ],
        "overall_pattern": "isolated surface anomaly",
        "overall_severity": "MINOR",
        "overall_confidence": 0.88,
        "total_power_impact_pct": 0.8,
        "healthy_areas_noted": "Primary bus and neighboring panel regions appear nominal.",
        "component_assessed": "solar_array",
        "degraded": degraded,
    }


def _environment_payload(*, degraded: bool = False) -> dict:
    return {
        "orbital_regime": "LEO",
        "altitude_km": 540.0,
        "inclination_deg": 53.2,
        "debris_flux_density": "moderate",
        "collision_probability": "low",
        "radiation_dose_rate": "low",
        "thermal_cycling_range": "-115C to +118C",
        "atomic_oxygen_flux": "high",
        "stressors": [
            {
                "name": "atomic_oxygen",
                "severity": "HIGH",
                "measured_value": "3.8e20 atoms/cm^2/s",
                "description": "Persistent erosion environment in LEO.",
                "source": "Deterministic E2E scenario",
            }
        ],
        "accelerating_factors": ["high orbital traffic"],
        "mitigating_factors": ["routine operator inspection cadence"],
        "data_sources": ["E2E stub"],
        "degraded": degraded,
    }


def _failure_mode_payload(*, degraded: bool = False) -> dict:
    return {
        "failure_mode": "surface_degradation",
        "mechanism": "cumulative environment exposure",
        "root_cause_chain": ["UV exposure", "atomic oxygen erosion"],
        "progression_rate": "SLOW",
        "power_degradation_estimate_pct": 1.1,
        "remaining_life_revision_years": 0.0,
        "time_to_critical": "Not currently projected",
        "historical_precedents": [
            {
                "event": "OrbitalNode-A panel inspection",
                "satellite": "OrbitalNode-A",
                "operator": "Orbital Compute Consortium",
                "year": "2026",
                "outcome": "Managed through monitoring cadence",
                "claim_amount_usd": "0",
                "relevance": "Comparable low-grade panel aging profile",
                "source": "internal_e2e",
            }
        ],
        "degraded": degraded,
    }


def _insurance_payload(
    *,
    risk_tier: str,
    composite: int,
    recommendation: str,
    summary: str,
    degraded: bool = False,
    evidence_gaps: list[str] | None = None,
    report_completeness: str = "COMPLETE",
) -> dict:
    return {
        "consistency_check": {
            "passed": True,
            "anomalies": [],
            "confidence_adjustment": "",
        },
        "risk_matrix": {
            "severity": {"score": 2, "reasoning": "Localized anomaly only."},
            "probability": {"score": 2, "reasoning": "Slow progression with monitoring."},
            "consequence": {"score": 4, "reasoning": "High-value orbital infrastructure node."},
            "composite": composite,
        },
        "risk_tier": risk_tier,
        "estimated_remaining_life_years": 5.5,
        "power_margin_percentage": 21.4,
        "annual_degradation_rate_pct": 1.3,
        "replacement_cost_usd": 420_000_000,
        "depreciated_value_usd": 315_000_000,
        "revenue_at_risk_annual_usd": 92_000_000,
        "total_loss_probability": 0.04,
        "underwriting_recommendation": recommendation,
        "recommendation_rationale": summary,
        "recommended_actions": [
            {
                "priority": "MEDIUM",
                "timeframe": "30 days",
                "action": "Perform targeted follow-up inspection",
                "rationale": "Track anomaly progression and confirm subsystem impact.",
            }
        ],
        "worst_case_scenario": "Gradual efficiency decline in exposed panel regions.",
        "summary": summary,
        "degraded": degraded,
        "evidence_gaps": evidence_gaps or [],
        "report_completeness": report_completeness,
    }


async def run_e2e_stub_pipeline(
    *,
    analysis_id: str,
    norad_id: str | None,
    additional_context: str,
) -> AsyncGenerator[dict, None]:
    """Emit deterministic SSE events for the requested E2E scenario."""
    scenario = _scenario_key(additional_context)
    seq = 0

    async def emit(event: AgentEvent) -> dict:
        nonlocal seq
        wrapped = _wrap_event(event, analysis_id, seq)
        seq += 1
        await asyncio.sleep(0.01)
        return wrapped

    for agent_name in AGENT_ORDER:
        yield await emit(AgentEvent.queued(agent_name))

    yield await emit(AgentEvent.thinking("orbital_classification", THINKING_MESSAGES["orbital_classification"]))
    classification = _classification_payload(norad_id, valid=scenario != "rejected")
    yield await emit(AgentEvent.complete("orbital_classification", classification))

    if scenario == "rejected":
        yield await emit(
            AgentEvent.error(
                "orbital_classification",
                classification["rejection_reason"],
                degraded=True,
            )
        )
        yield format_sse_done("rejected")
        return

    yield await emit(AgentEvent.thinking("satellite_vision", THINKING_MESSAGES["satellite_vision"]))
    if scenario == "partial":
        yield await emit(
            AgentEvent.error(
                "satellite_vision",
                "Satellite vision evidence degraded in deterministic E2E scenario.",
                degraded=True,
            )
        )
    else:
        yield await emit(AgentEvent.complete("satellite_vision", _vision_payload()))

    yield await emit(AgentEvent.thinking("orbital_environment", THINKING_MESSAGES["orbital_environment"]))
    yield await emit(AgentEvent.complete("orbital_environment", _environment_payload()))

    yield await emit(AgentEvent.thinking("failure_mode", THINKING_MESSAGES["failure_mode"]))
    yield await emit(AgentEvent.complete("failure_mode", _failure_mode_payload()))

    yield await emit(AgentEvent.thinking("insurance_risk", THINKING_MESSAGES["insurance_risk"]))

    if scenario == "failed":
        yield await emit(
            AgentEvent.error(
                "insurance_risk",
                "Underwriting model failed in deterministic E2E scenario.",
                degraded=True,
            )
        )
        yield format_sse_error("Underwriting model failed in deterministic E2E scenario.")
        yield format_sse_done("failed")
        return

    if scenario == "partial":
        yield await emit(
            AgentEvent.complete(
                "insurance_risk",
                _insurance_payload(
                    risk_tier="MEDIUM",
                    composite=34,
                    recommendation="FURTHER_INVESTIGATION",
                    summary="Incomplete evidence requires further investigation before underwriting.",
                    degraded=True,
                    evidence_gaps=["satellite_vision"],
                    report_completeness="PARTIAL",
                ),
                degraded=True,
            )
        )
        yield format_sse_done("completed_partial")
        return

    yield await emit(
        AgentEvent.complete(
            "insurance_risk",
            _insurance_payload(
                risk_tier="LOW",
                composite=16,
                recommendation="INSURABLE_STANDARD",
                summary="Deterministic E2E success scenario indicates low underwriting impact.",
            ),
        )
    )
    yield format_sse_done("completed")
