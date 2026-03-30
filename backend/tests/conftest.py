import os
import pytest

# Set dummy env vars before any backend module imports trigger Settings()
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")


@pytest.fixture
def sample_image_bytes():
    """Minimal valid JPEG for testing (1x1 pixel)."""
    # Smallest valid JPEG
    return bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0x7B, 0x94,
        0x11, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xD9
    ])


@pytest.fixture
def sample_classification_result():
    return {
        "valid": True,
        "satellite_type": "communications",
        "bus_platform": "SSL-1300",
        "orbital_regime": "GEO",
        "expected_components": ["solar_array", "antenna_reflector", "bus"],
        "design_life_years": 15.0,
        "estimated_age_years": 8.0,
        "operator": "SES",
        "notes": "",
        "degraded": False,
    }


@pytest.fixture
def sample_vision_result():
    return {
        "damages": [
            {
                "id": 1,
                "type": "micrometeorite_crater",
                "description": "Small impact crater on solar cell",
                "bounding_box": [100, 200, 150, 250],
                "label": "Impact crater",
                "severity": "MINOR",
                "confidence": 0.85,
                "uncertain": False,
                "estimated_power_impact_pct": 0.5,
            }
        ],
        "overall_pattern": "isolated micrometeorite impact",
        "overall_severity": "MINOR",
        "overall_confidence": 0.85,
        "total_power_impact_pct": 0.5,
        "healthy_areas_noted": "Most of solar array appears nominal",
        "component_assessed": "solar_array",
        "degraded": False,
    }


@pytest.fixture
def sample_insurance_risk_result():
    return {
        "consistency_check": {"passed": True, "anomalies": [], "confidence_adjustment": ""},
        "risk_matrix": {
            "severity": {"score": 2, "reasoning": "Minor damage only"},
            "probability": {"score": 2, "reasoning": "Slow progression"},
            "consequence": {"score": 3, "reasoning": "GEO comms satellite"},
            "composite": 12,
        },
        "risk_tier": "LOW",
        "estimated_remaining_life_years": 7.0,
        "power_margin_percentage": 25.0,
        "annual_degradation_rate_pct": 2.0,
        "replacement_cost_usd": 350000000,
        "depreciated_value_usd": 163000000,
        "revenue_at_risk_annual_usd": 120000000,
        "total_loss_probability": 0.05,
        "underwriting_recommendation": "INSURABLE_STANDARD",
        "recommendation_rationale": "Minor damage consistent with nominal aging",
        "recommended_actions": [],
        "worst_case_scenario": "Continued micrometeorite bombardment",
        "summary": "Satellite in good condition",
        "degraded": False,
        "evidence_gaps": [],
        "report_completeness": "COMPLETE",
    }
