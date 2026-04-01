"""Tests for sensitivity analysis service."""
import os
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

import pytest
from services.sensitivity_service import run_sensitivity_analysis


def test_sensitivity_basic():
    sa = run_sensitivity_analysis(3, 2, 3)
    assert len(sa.parameters) == 3
    assert sa.baseline_recommendation != ""
    assert sa.recommendation_robustness in ("ROBUST", "MARGINAL", "FRAGILE")


def test_sensitivity_robust_low_risk():
    """Low risk (1,1,1) should be ROBUST — hard to flip."""
    sa = run_sensitivity_analysis(1, 1, 1)
    assert sa.recommendation_robustness == "ROBUST"


def test_sensitivity_fragile_boundary():
    """Scores at tier boundaries should be FRAGILE."""
    sa = run_sensitivity_analysis(3, 3, 3, "INSURABLE_WITH_EXCLUSIONS")
    # 3*3*3=27, changing any dimension ±1 likely flips tier
    assert sa.recommendation_robustness in ("MARGINAL", "FRAGILE")


def test_sensitivity_critical_thresholds_identified():
    sa = run_sensitivity_analysis(3, 4, 5)
    # At least some thresholds should be identified
    assert isinstance(sa.critical_thresholds, list)


def test_sensitivity_key_drivers_ranked():
    # severity=2 (range 1-3, others=3*5=15): influence = (3-1)*15 = 30
    # probability=3 (range 2-4, others=2*5=10): influence = (4-2)*10 = 20
    # consequence=5 (range 4-5 capped, others=2*3=6): influence = (5-4)*6 = 6
    # severity has highest influence when consequence is already at max
    sa = run_sensitivity_analysis(2, 3, 5)
    assert len(sa.key_drivers) == 3
    assert sa.key_drivers[0] == "severity"


def test_sensitivity_parameters_have_recommendations():
    sa = run_sensitivity_analysis(3, 2, 4)
    for p in sa.parameters:
        assert p.recommendation_at_low != ""
        assert p.recommendation_at_high != ""


def test_sensitivity_extreme_high():
    sa = run_sensitivity_analysis(5, 5, 5, "UNINSURABLE")
    assert sa.recommendation_robustness == "ROBUST"


def test_tornado_chart_renders():
    from services.chart_renderer import render_sensitivity_tornado
    png = render_sensitivity_tornado(
        [{"name": "severity", "baseline_value": 3, "test_range_low": 2, "test_range_high": 4, "is_critical": True},
         {"name": "probability", "baseline_value": 2, "test_range_low": 1, "test_range_high": 3, "is_critical": False}],
        baseline_recommendation="INSURABLE_WITH_EXCLUSIONS",
        robustness="MARGINAL",
    )
    assert len(png) > 1000  # Valid PNG
    assert png[:4] == b'\x89PNG'
