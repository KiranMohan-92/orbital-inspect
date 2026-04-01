"""
Sensitivity analysis — test how conclusions change with input variations.

Pure server-side computation (no LLM). Takes an InsuranceRiskReport and
re-runs the risk scoring with perturbed parameters to identify critical
thresholds where the underwriting recommendation would change.
"""

import logging
from models.provenance import SensitivityParameter, SensitivityAnalysis

log = logging.getLogger(__name__)


def _composite_to_tier(composite: int) -> str:
    if composite <= 15: return "LOW"
    if composite <= 35: return "MEDIUM"
    if composite <= 60: return "MEDIUM-HIGH"
    if composite <= 90: return "HIGH"
    return "CRITICAL"


def _tier_to_recommendation(tier: str) -> str:
    return {
        "LOW": "INSURABLE_STANDARD",
        "MEDIUM": "INSURABLE_ELEVATED_PREMIUM",
        "MEDIUM-HIGH": "INSURABLE_WITH_EXCLUSIONS",
        "HIGH": "FURTHER_INVESTIGATION",
        "CRITICAL": "UNINSURABLE",
    }.get(tier, "FURTHER_INVESTIGATION")


def run_sensitivity_analysis(
    severity: int,
    probability: int,
    consequence: int,
    baseline_recommendation: str = "",
) -> SensitivityAnalysis:
    """
    Sweep risk matrix parameters and identify critical thresholds.

    Tests each dimension at ±1 and ±2 from baseline, computing the
    composite score and resulting recommendation at each point.
    """
    baseline_composite = severity * probability * consequence
    baseline_tier = _composite_to_tier(baseline_composite)
    if not baseline_recommendation:
        baseline_recommendation = _tier_to_recommendation(baseline_tier)

    parameters = []
    critical_thresholds = []
    key_drivers = []

    for dim_name, baseline_val, other_a, other_b in [
        ("severity", severity, probability, consequence),
        ("probability", probability, severity, consequence),
        ("consequence", consequence, severity, probability),
    ]:
        low_val = max(1, baseline_val - 1)
        high_val = min(5, baseline_val + 1)

        low_composite = low_val * other_a * other_b
        high_composite = high_val * other_a * other_b

        low_rec = _tier_to_recommendation(_composite_to_tier(low_composite))
        high_rec = _tier_to_recommendation(_composite_to_tier(high_composite))

        is_critical = (low_rec != baseline_recommendation) or (high_rec != baseline_recommendation)

        param = SensitivityParameter(
            name=dim_name,
            baseline_value=baseline_val,
            test_range_low=low_val,
            test_range_high=high_val,
            recommendation_at_low=low_rec,
            recommendation_at_high=high_rec,
            is_critical=is_critical,
        )
        parameters.append(param)

        if is_critical:
            if low_rec != baseline_recommendation:
                critical_thresholds.append(f"{dim_name} = {low_val} → {low_rec}")
            if high_rec != baseline_recommendation:
                critical_thresholds.append(f"{dim_name} = {high_val} → {high_rec}")

        # Measure influence: how much does composite change per unit
        influence = abs(high_composite - low_composite)
        key_drivers.append((dim_name, influence))

    # Rank by influence
    key_drivers.sort(key=lambda x: -x[1])
    ranked_drivers = [name for name, _ in key_drivers]

    # Determine robustness
    critical_count = sum(1 for p in parameters if p.is_critical)
    if critical_count == 0:
        robustness = "ROBUST"
    elif critical_count <= 1:
        robustness = "MARGINAL"
    else:
        robustness = "FRAGILE"

    return SensitivityAnalysis(
        parameters=parameters,
        baseline_recommendation=baseline_recommendation,
        recommendation_robustness=robustness,
        critical_thresholds=critical_thresholds,
        key_drivers=ranked_drivers,
    )
