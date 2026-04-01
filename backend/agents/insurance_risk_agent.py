"""
Insurance Risk Agent — the key differentiator of Orbital Inspect.

Synthesizes all upstream agent outputs into an actuarial-grade risk assessment
with underwriting recommendation, financial exposure estimates, and consistency
cross-validation. This agent's output is what insurers pay $50K-500K for.
"""

import logging
from pathlib import Path
from services.gemini_service import (
    is_adk_available,
    run_adk_agent,
    get_model_name,
    parse_json_response,
)
from models.satellite import InsuranceRiskReport
from models.provenance import (
    DataSourceType, ConfidenceCalibration, FinancialEstimate,
    LossProbabilityDerivation, SensitivityAnalysis, FieldProvenance,
)

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "insurance_risk_prompt.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text()


def _build_agent():
    if not is_adk_available():
        return None

    from google.adk.agents import Agent

    return Agent(
        name="insurance_risk_agent",
        model=get_model_name(),
        instruction=_PROMPT_TEMPLATE,
        output_key="insurance_risk_output",
    )


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


async def assess_insurance_risk(
    classification_context: str = "",
    vision_context: str = "",
    environment_context: str = "",
    failure_mode_context: str = "",
) -> InsuranceRiskReport:
    """
    Generate an actuarial-grade insurance risk assessment.

    This is the culminating agent — it receives ALL upstream data and produces
    the underwriting recommendation that insurers act on.

    Args:
        classification_context: JSON from Classification Agent
        vision_context: JSON from Vision Agent
        environment_context: JSON from Environment Agent
        failure_mode_context: JSON from Failure Mode Agent

    Returns:
        InsuranceRiskReport with risk matrix, metrics, and underwriting recommendation
    """
    prompt = (
        "Generate a comprehensive insurance risk assessment for this satellite.\n\n"
        f"=== SATELLITE CLASSIFICATION ===\n{classification_context}\n\n"
        f"=== VISUAL DAMAGE ASSESSMENT ===\n{vision_context}\n\n"
        f"=== ORBITAL ENVIRONMENT ===\n{environment_context}\n\n"
        f"=== FAILURE MODE ANALYSIS ===\n{failure_mode_context}\n\n"
        "Provide your complete risk matrix, insurance metrics, and underwriting recommendation."
    )

    agent = _get_agent()

    try:
        data = await run_adk_agent(
            agent, prompt
        ) if agent else await _fallback(prompt)

        report = InsuranceRiskReport(**data)

        # Server-side consistency enforcement
        report = _enforce_consistency(report)
        report = _validate_provenance(report)
        return report
    except Exception as e:
        log.error("Insurance risk assessment failed", exc_info=True)
        return InsuranceRiskReport(
            consistency_check={"passed": False, "anomalies": ["Agent processing error"], "confidence_adjustment": "LOW"},
            risk_matrix={
                "severity": {"score": 3, "reasoning": "Unable to assess — agent error"},
                "probability": {"score": 3, "reasoning": "Unable to assess — agent error"},
                "consequence": {"score": 3, "reasoning": "Unable to assess — agent error"},
                "composite": 27,
            },
            risk_tier="MEDIUM",
            underwriting_recommendation="FURTHER_INVESTIGATION",
            recommendation_rationale="Assessment could not be completed due to a processing error. Manual review required.",
            summary="Automated assessment encountered an error. Recommend manual underwriting review.",
            degraded=True,
        )


def _enforce_consistency(report: InsuranceRiskReport) -> InsuranceRiskReport:
    """
    Server-side consistency checks on the insurance risk report.

    Validates that composite = S×P×C, risk_tier matches composite,
    and recommendation aligns with tier.
    """
    anomalies = list(report.consistency_check.anomalies) if report.consistency_check else []
    rm = report.risk_matrix

    # Check 1: Composite must equal S × P × C
    expected_composite = rm.severity.score * rm.probability.score * rm.consequence.score
    if rm.composite != expected_composite:
        anomalies.append(
            f"Composite mismatch: reported {rm.composite}, expected {expected_composite} "
            f"({rm.severity.score}×{rm.probability.score}×{rm.consequence.score})"
        )
        rm.composite = expected_composite

    # Check 2: Risk tier must match composite
    expected_tier = _composite_to_tier(rm.composite)
    if report.risk_tier != expected_tier:
        anomalies.append(f"Tier mismatch: reported {report.risk_tier}, expected {expected_tier} for composite {rm.composite}")
        report.risk_tier = expected_tier

    # Check 3: Recommendation alignment
    recommendation = report.underwriting_recommendation
    if rm.composite > 80 and recommendation in ("INSURABLE_STANDARD", "INSURABLE_ELEVATED_PREMIUM"):
        anomalies.append(f"Recommendation too lenient: {recommendation} with composite {rm.composite}")
        report.underwriting_recommendation = "UNINSURABLE"
    elif rm.composite <= 15 and recommendation == "UNINSURABLE":
        anomalies.append(f"Recommendation too harsh: UNINSURABLE with composite {rm.composite}")
        report.underwriting_recommendation = "INSURABLE_STANDARD"

    # Update consistency check
    if report.consistency_check is not None:
        report.consistency_check.passed = len(anomalies) == 0
        report.consistency_check.anomalies = anomalies
        if anomalies:
            report.consistency_check.confidence_adjustment = "Server-side corrections applied"

    return report


def _validate_provenance(report: InsuranceRiskReport) -> InsuranceRiskReport:
    """
    Ensure provenance fields have at least stub values when the LLM omits them.

    This is the key safety mechanism — reports ALWAYS render, even if the agent
    completely ignores the provenance prompt. Stubs are transparent: they say
    'no attribution provided' rather than fabricating sources.
    """
    if report.confidence_calibration is None:
        report.confidence_calibration = ConfidenceCalibration(
            basis="No structured calibration provided by agent — treat all estimates as approximate",
        )

    if report.replacement_cost_usd is not None and not report.replacement_cost_detail:
        report.replacement_cost_detail = FinancialEstimate(
            value_usd=report.replacement_cost_usd,
            source="agent_estimate",
            derivation="No structured attribution provided — verify with operator/broker",
        )

    if report.depreciated_value_usd is not None and not report.depreciated_value_detail:
        report.depreciated_value_detail = FinancialEstimate(
            value_usd=report.depreciated_value_usd,
            source="agent_estimate",
            derivation="No structured attribution provided",
        )

    if report.revenue_at_risk_annual_usd is not None and not report.revenue_at_risk_detail:
        report.revenue_at_risk_detail = FinancialEstimate(
            value_usd=report.revenue_at_risk_annual_usd,
            source="agent_estimate",
            derivation="No structured attribution provided",
        )

    if report.total_loss_probability is not None and not report.loss_probability_derivation:
        report.loss_probability_derivation = LossProbabilityDerivation(
            total_loss_probability=report.total_loss_probability,
            derivation_narrative="No structured derivation provided — probability is an agent estimate without explicit base rates",
        )

    # Stub FieldProvenance for key metrics
    stub_prov = FieldProvenance(
        source_type=DataSourceType.ESTIMATED,
        primary_source="agent_inference",
        caveats=["No structured provenance provided by agent"],
    )
    if report.estimated_remaining_life_years is not None and not report.remaining_life_provenance:
        report.remaining_life_provenance = stub_prov.model_copy()
    if report.power_margin_percentage is not None and not report.power_margin_provenance:
        report.power_margin_provenance = stub_prov.model_copy()
    if report.annual_degradation_rate_pct is not None and not report.degradation_rate_provenance:
        report.degradation_rate_provenance = stub_prov.model_copy()

    return report


def _composite_to_tier(composite: int) -> str:
    if composite <= 15:
        return "LOW"
    if composite <= 35:
        return "MEDIUM"
    if composite <= 60:
        return "MEDIUM-HIGH"
    if composite <= 90:
        return "HIGH"
    return "CRITICAL"


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
