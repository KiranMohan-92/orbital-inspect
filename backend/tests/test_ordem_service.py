"""Tests for the NASA ORDEM debris/radiation/thermal service."""
import pytest
from services.ordem_service import (
    lookup_debris_flux,
    get_debris_severity,
    lookup_radiation,
    lookup_thermal,
    format_flux_summary,
)


# ─── lookup_debris_flux ──────────────────────────────────────────────────────

def test_lookup_debris_flux_leo_400km():
    """400 km is in the 400-600 band."""
    band = lookup_debris_flux(400)
    assert band is not None
    assert band.altitude_min_km == 400
    assert band.altitude_max_km == 600
    assert band.flux_1mm == pytest.approx(5.5e-5)


def test_lookup_debris_flux_geo_35786km():
    """GEO at 35786 km is in the 35000-36500 band."""
    band = lookup_debris_flux(35786)
    assert band is not None
    assert band.altitude_min_km == 35000
    assert band.altitude_max_km == 36500
    assert band.flux_1mm == pytest.approx(1.0e-5)


def test_lookup_debris_flux_unknown_altitude():
    """Altitude between GEO and MEO (e.g. 25000 km) has no band."""
    band = lookup_debris_flux(25000)
    assert band is None


def test_lookup_debris_flux_lower_leo_boundary():
    """200 km is the start of the first band."""
    band = lookup_debris_flux(200)
    assert band is not None
    assert band.altitude_min_km == 200


def test_lookup_debris_flux_meo():
    """5000 km is in the MEO band (2000-20000)."""
    band = lookup_debris_flux(5000)
    assert band is not None
    assert band.altitude_min_km == 2000
    assert band.altitude_max_km == 20000


# ─── get_debris_severity ─────────────────────────────────────────────────────

def test_get_debris_severity_leo_high_density():
    """800-1000 km band has flux_1mm=2.8e-4, which is >= 2.0e-4 → CRITICAL."""
    severity = get_debris_severity(900)
    assert severity == "CRITICAL"


def test_get_debris_severity_leo_high():
    """600-800 km band has flux_1mm=1.2e-4, which is >= 1.0e-4 → HIGH."""
    severity = get_debris_severity(700)
    assert severity == "HIGH"


def test_get_debris_severity_medium():
    """400-600 km band has flux_1mm=5.5e-5, which is >= 5.0e-5 → MEDIUM."""
    severity = get_debris_severity(500)
    assert severity == "MEDIUM"


def test_get_debris_severity_low():
    """GEO band has flux_1mm=1.0e-5, which is < 5.0e-5 → LOW."""
    severity = get_debris_severity(35786)
    assert severity == "LOW"


def test_get_debris_severity_unknown_altitude():
    """Altitude with no band returns UNKNOWN."""
    severity = get_debris_severity(25000)
    assert severity == "UNKNOWN"


# ─── lookup_radiation ────────────────────────────────────────────────────────

def test_lookup_radiation_leo_low():
    """Below 600 km → LEO_LOW."""
    data = lookup_radiation(400)
    assert data is not None
    assert data["altitude_range"] == "200-600 km"
    assert data["annual_dose_krad"] == 5.0


def test_lookup_radiation_leo_high():
    """600-1200 km → LEO_HIGH."""
    data = lookup_radiation(800)
    assert data is not None
    assert data["altitude_range"] == "600-1200 km"
    assert data["annual_dose_krad"] == 20.0


def test_lookup_radiation_meo():
    """2000-20000 km → MEO."""
    data = lookup_radiation(10000)
    assert data is not None
    assert data["altitude_range"] == "2000-20000 km"
    assert data["annual_dose_krad"] == 100.0


def test_lookup_radiation_geo():
    """35000+ km → GEO."""
    data = lookup_radiation(35786)
    assert data is not None
    assert data["altitude_range"] == "35000-36500 km"
    assert data["annual_dose_krad"] == 30.0


def test_lookup_radiation_gap_returns_none():
    """Altitude 20000-35000 km has no radiation data → None."""
    data = lookup_radiation(25000)
    assert data is None


# ─── lookup_thermal ──────────────────────────────────────────────────────────

def test_lookup_thermal_leo():
    data = lookup_thermal("LEO")
    assert data is not None
    assert data["cycles_per_day"] == 15.5
    assert data["min_temp_c"] == -150


def test_lookup_thermal_geo():
    data = lookup_thermal("GEO")
    assert data is not None
    assert data["cycles_per_day"] == 1.0
    assert data["min_temp_c"] == -196


def test_lookup_thermal_meo():
    data = lookup_thermal("MEO")
    assert data is not None
    assert data["cycles_per_day"] == 4.0


def test_lookup_thermal_heo():
    data = lookup_thermal("HEO")
    assert data is not None
    assert data["cycles_per_day"] == 2.0


def test_lookup_thermal_sso_maps_to_leo():
    """SSO should map to LEO thermal profile."""
    sso_data = lookup_thermal("SSO")
    leo_data = lookup_thermal("LEO")
    assert sso_data == leo_data


def test_lookup_thermal_unknown_returns_none():
    data = lookup_thermal("UNKNOWN")
    assert data is None


def test_lookup_thermal_case_insensitive():
    data = lookup_thermal("leo")
    assert data is not None
    assert data["cycles_per_day"] == 15.5


# ─── format_flux_summary ─────────────────────────────────────────────────────

def test_format_flux_summary_produces_readable_output():
    summary = format_flux_summary(400)
    assert "ORDEM 4.0" in summary
    assert "400 km" in summary
    assert "particles/m²/year" in summary
    assert "MEDIUM" in summary


def test_format_flux_summary_no_data():
    summary = format_flux_summary(25000)
    assert "No ORDEM data" in summary
    assert "25000" in summary


def test_format_flux_summary_geo():
    summary = format_flux_summary(35786)
    assert "35786 km" in summary
    assert "LOW" in summary
