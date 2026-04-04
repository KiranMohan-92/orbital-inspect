"""Tests for telemetry proxy services."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

import pytest

from services.conjunction_service import (
    ConjunctionEvent,
    calculate_conjunction_risk,
)
from services.enhanced_weather_service import (
    _extract_latest_bz,
    fetch_enhanced_space_weather,
)
from services.space_weather_service import SpaceWeatherSnapshot, _extract_latest_kp, fetch_space_weather
from services.tle_history_service import EARTH_MU_KM3_S2, EARTH_RADIUS_KM, analyze_tle_records


def _mean_motion_for_altitude(altitude_km: float) -> float:
    semi_major_axis = EARTH_RADIUS_KM + altitude_km
    radians_per_second = math.sqrt(EARTH_MU_KM3_S2 / (semi_major_axis ** 3))
    return radians_per_second * 86400.0 / (2.0 * math.pi)


def _tle_record(
    epoch: datetime,
    altitude_km: float,
    eccentricity: float,
    inclination_deg: float,
) -> dict[str, float | str]:
    return {
        "EPOCH": epoch.isoformat(),
        "MEAN_MOTION": _mean_motion_for_altitude(altitude_km),
        "ECCENTRICITY": eccentricity,
        "INCLINATION": inclination_deg,
        "APOAPSIS": altitude_km + 2.0,
        "PERIAPSIS": altitude_km - 2.0,
    }


@pytest.mark.asyncio
async def test_tle_history_analyzer_scores_stable_orbit_high():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = [
        _tle_record(start + timedelta(days=index * 10), altitude, 0.0002 + index * 1e-5, 97.4000 + index * 2e-4)
        for index, altitude in enumerate([550.0, 549.9, 549.8, 549.7, 549.6, 549.5])
    ]

    analysis = await analyze_tle_records("12345", records, days=90)

    assert analysis.sample_count == 6
    assert analysis.maneuver_count == 0
    assert analysis.orbit_decay_rate_km_per_day < 0
    assert analysis.altitude_stability_km < 1.0
    assert analysis.overall_health_score >= 80
    assert analysis.health_rating in {"EXCELLENT", "GOOD"}


@pytest.mark.asyncio
async def test_tle_history_analyzer_detects_maneuver_from_discontinuity():
    start = datetime(2026, 2, 1, tzinfo=timezone.utc)
    altitudes = [540.0, 539.9, 539.7, 552.5, 552.3, 552.1]
    eccentricities = [0.0002, 0.00022, 0.00024, 0.0011, 0.00112, 0.00115]
    inclinations = [97.5, 97.5002, 97.5004, 97.56, 97.5601, 97.5602]
    records = [
        _tle_record(
            start + timedelta(days=index * 7),
            altitudes[index],
            eccentricities[index],
            inclinations[index],
        )
        for index in range(len(altitudes))
    ]

    analysis = await analyze_tle_records("67890", records, days=90)

    assert analysis.sample_count == 6
    assert analysis.maneuver_count >= 1
    assert analysis.detected_maneuvers[0].estimated_delta_v_m_s > 0
    assert analysis.maximum_altitude_km > analysis.minimum_altitude_km
    assert analysis.overall_health_score < 90


@pytest.mark.asyncio
async def test_extract_latest_bz_uses_latest_non_null_measurement():
    payload = [
        ["time_tag", "bx_gsm", "by_gsm", "bz_gsm", "lon_gsm", "lat_gsm", "bt"],
        ["2026-04-01 10:00:00.000", "1.0", "2.0", "", "0", "0", "5.0"],
        ["2026-04-01 10:01:00.000", "1.5", "2.5", "-7.5", "0", "0", "8.4"],
    ]

    bz_nt, bt_nt = await _extract_latest_bz(payload)

    assert bz_nt == pytest.approx(-7.5)
    assert bt_nt == pytest.approx(8.4)


def test_extract_latest_kp_supports_new_noaa_mapping_payload():
    payload = [
        {"time_tag": "2026-04-01T09:00:00Z", "Kp": "2.67"},
        {"time_tag": "2026-04-01T12:00:00Z", "Kp": "4.33"},
    ]

    kp_value = _extract_latest_kp(payload)

    assert kp_value == pytest.approx(4.33)


def test_extract_latest_kp_supports_tabular_payload():
    payload = [
        ["time_tag", "kp_index"],
        ["2026-04-01 09:00:00.000", "3.0"],
        ["2026-04-01 12:00:00.000", "5.67"],
    ]

    kp_value = _extract_latest_kp(payload)

    assert kp_value == pytest.approx(5.67)


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeAsyncClient:
    def __init__(self, payloads):
        self.payloads = payloads

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None):
        if url not in self.payloads:
            return _FakeResponse([], status_code=404)
        return _FakeResponse(self.payloads[url])


@pytest.mark.asyncio
async def test_enhanced_weather_parses_bz_and_classifies_alerts(monkeypatch):
    async def fake_fetch_space_weather():
        return SpaceWeatherSnapshot(
            kp_index=4.0,
            kp_category="ACTIVE",
            solar_wind_speed_km_s=550.0,
            solar_wind_density_p_cm3=6.0,
            proton_flux_pfu=12.0,
            xray_flux=2e-5,
            flare_class="M",
            storm_warning=True,
            data_sources=["baseline"],
        )

    payloads = {
        "https://services.swpc.noaa.gov/products/solar-wind/mag-7-day.json": [
            ["time_tag", "bx_gsm", "by_gsm", "bz_gsm", "lon_gsm", "lat_gsm", "bt"],
            ["2026-04-01 11:59:00.000", "1.0", "2.0", "-9.0", "0", "0", "11.0"],
        ],
        "https://services.swpc.noaa.gov/products/alerts.json": [
            {
                "product_id": "A30F",
                "issue_datetime": "2026-04-01 13:30:37.470",
                "message": (
                    "Space Weather Message Code: WATA30\n"
                    "Serial Number: 3663\n"
                    "Issue Time: 2026 Apr 01 1330 UTC\n\n"
                    "WARNING: Geomagnetic Storm Category G2 Predicted\n"
                    "Potential Impacts: Satellite orientation irregularities may occur."
                ),
            }
        ],
        "https://services.swpc.noaa.gov/products/forecasts/3-day-outlook.json": [
            {"date": "2026-04-01", "geomagnetic_activity": "Active"},
            {"date": "2026-04-02", "geomagnetic_activity": "Minor Storm"},
        ],
        "https://services.swpc.noaa.gov/products/forecasts/27-day-outlook.json": {
            "periods": [
                {"date": "2026-04-01", "activity": "Elevated"},
                {"date": "2026-04-02", "activity": "Elevated"},
            ]
        },
    }

    monkeypatch.setattr("services.enhanced_weather_service.fetch_space_weather", fake_fetch_space_weather)
    monkeypatch.setattr(
        "services.enhanced_weather_service.httpx.AsyncClient",
        lambda timeout: _FakeAsyncClient(payloads),
    )

    snapshot = await fetch_enhanced_space_weather()

    assert snapshot.bz_nt == pytest.approx(-9.0)
    assert snapshot.geoeffective is True
    assert snapshot.bz_orientation == "SOUTHWARD"
    assert snapshot.highest_alert_level == "WARNING"
    assert len(snapshot.active_alerts) == 1
    assert snapshot.active_alerts[0]["level"] == "WARNING"
    assert len(snapshot.three_day_forecast) == 2
    assert len(snapshot.twenty_seven_day_outlook) == 2


@pytest.mark.asyncio
async def test_fetch_space_weather_supports_new_noaa_kp_mapping_payload(monkeypatch):
    payloads = {
        "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json": [
            {"time_tag": "2026-04-01T09:00:00Z", "Kp": "2.67"},
            {"time_tag": "2026-04-01T12:00:00Z", "Kp": "5.33"},
        ],
        "https://services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json": [
            ["time_tag", "density", "speed"],
            ["2026-04-01 12:00:00.000", "6.1", "510.0"],
        ],
        "https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json": [
            {"time_tag": "2026-04-01T12:00:00Z", "flux": 1.2e-5},
        ],
        "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-6-hour.json": [
            {"time_tag": "2026-04-01T12:00:00Z", "energy": ">=10 MeV", "flux": 12.5},
        ],
    }

    monkeypatch.setattr(
        "services.space_weather_service.httpx.AsyncClient",
        lambda timeout: _FakeAsyncClient(payloads),
    )

    snapshot = await fetch_space_weather()

    assert snapshot.kp_index == pytest.approx(5.33)
    assert snapshot.kp_category == "ACTIVE"
    assert snapshot.solar_wind_density_p_cm3 == pytest.approx(6.1)
    assert snapshot.solar_wind_speed_km_s == pytest.approx(510.0)
    assert snapshot.flare_class == "M"
    assert snapshot.proton_flux_pfu == pytest.approx(12.5)
    assert snapshot.storm_warning is True
    assert "NOAA Planetary K-index" in snapshot.data_sources


@pytest.mark.asyncio
async def test_conjunction_risk_score_reflects_frequency_and_close_misses():
    events = [
        ConjunctionEvent(
            tca="2026-04-01T12:00:00+00:00",
            miss_distance_km=0.8,
            relative_speed_km_s=12.5,
            collision_probability=2e-5,
            counterparty_norad_id="90001",
            counterparty_name="TEST DEB",
            is_debris=True,
            severity="HIGH",
        ),
        ConjunctionEvent(
            tca="2026-04-02T12:00:00+00:00",
            miss_distance_km=3.2,
            relative_speed_km_s=11.0,
            collision_probability=7e-6,
            counterparty_norad_id="90001",
            counterparty_name="TEST DEB",
            is_debris=True,
            severity="MEDIUM",
        ),
        ConjunctionEvent(
            tca="2026-04-03T12:00:00+00:00",
            miss_distance_km=6.5,
            relative_speed_km_s=9.4,
            collision_probability=1e-6,
            counterparty_norad_id="90002",
            counterparty_name="PAYLOAD",
            is_debris=False,
            severity="MEDIUM",
        ),
    ]

    assessment = await calculate_conjunction_risk("25544", events)

    assert assessment.event_count == 3
    assert assessment.minimum_miss_distance_km == pytest.approx(0.8)
    assert assessment.average_miss_distance_km == pytest.approx((0.8 + 3.2 + 6.5) / 3, rel=1e-3)
    assert assessment.conjunction_risk_score >= 60
    assert assessment.most_threatening_objects[0]["counterparty_norad_id"] == "90001"
    assert assessment.most_threatening_objects[0]["event_count"] == 2
