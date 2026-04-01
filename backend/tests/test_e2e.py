import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

import httpx
import pytest
import pytest_asyncio

import main
from main import app
from models.events import AgentEvent
from services.conjunction_service import ConjunctionEvent, calculate_conjunction_risk
from services.enhanced_weather_service import _extract_latest_bz, fetch_enhanced_space_weather
from services.space_weather_service import SpaceWeatherSnapshot
from services.sse_service import format_sse_done, format_sse_event
from services.tle_history_service import EARTH_MU_KM3_S2, EARTH_RADIUS_KM, analyze_tle_records


AGENT_ORDER = [
    "orbital_classification",
    "satellite_vision",
    "orbital_environment",
    "failure_mode",
    "insurance_risk",
]


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def reset_webhooks(monkeypatch):
    import api.webhooks as webhooks_api

    monkeypatch.setattr(webhooks_api, "_webhooks", {})
    monkeypatch.setattr(webhooks_api, "_next_id", 1)


def _fake_pipeline_payloads():
    return {
        "orbital_classification": {
            "valid": True,
            "satellite_type": "space_station",
            "bus_platform": "ISS Integrated Truss",
            "orbital_regime": "LEO",
            "expected_components": ["solar_array", "truss", "pressurized_module"],
            "design_life_years": 15.0,
            "estimated_age_years": 27.0,
            "operator": "NASA / Roscosmos / International Partners",
            "notes": "NORAD 25544 identified as the International Space Station.",
            "degraded": False,
        },
        "satellite_vision": {
            "damages": [
                {
                    "id": 1,
                    "type": "panel_surface_anomaly",
                    "description": "Localized discoloration on solar array blanket.",
                    "bounding_box": [112, 204, 188, 286],
                    "label": "Surface anomaly",
                    "severity": "MINOR",
                    "confidence": 0.82,
                    "uncertain": False,
                    "estimated_power_impact_pct": 0.4,
                }
            ],
            "overall_pattern": "isolated surface anomaly",
            "overall_severity": "MINOR",
            "overall_confidence": 0.82,
            "total_power_impact_pct": 0.4,
            "healthy_areas_noted": "Primary truss and adjacent panels appear nominal.",
            "component_assessed": "solar_array",
            "degraded": False,
        },
        "orbital_environment": {
            "orbital_regime": "LEO",
            "altitude_km": 420.0,
            "inclination_deg": 51.6,
            "debris_flux_density": "elevated",
            "collision_probability": "moderate",
            "radiation_dose_rate": "low",
            "thermal_cycling_range": "-120C to +120C",
            "atomic_oxygen_flux": "high",
            "stressors": [
                {
                    "name": "atomic_oxygen",
                    "severity": "HIGH",
                    "measured_value": "4.1e20 atoms/cm^2/s",
                    "description": "Persistent LEO erosion environment.",
                    "source": "NOAA/ORDEM",
                }
            ],
            "accelerating_factors": ["high orbital traffic"],
            "mitigating_factors": ["routine ISS maintenance"],
            "data_sources": ["CelesTrak", "NOAA SWPC", "NASA ORDEM"],
            "degraded": False,
        },
        "failure_mode": {
            "failure_mode": "surface_degradation",
            "mechanism": "cumulative space environment exposure",
            "root_cause_chain": ["UV exposure", "atomic oxygen erosion"],
            "progression_rate": "SLOW",
            "power_degradation_estimate_pct": 0.5,
            "remaining_life_revision_years": 0.0,
            "time_to_critical": "Not currently projected",
            "historical_precedents": [
                {
                    "event": "ISS solar blanket wear tracking",
                    "satellite": "ISS",
                    "operator": "NASA",
                    "year": "2024",
                    "outcome": "Managed through routine maintenance",
                    "claim_amount_usd": "0",
                    "relevance": "Similar low-grade panel aging in LEO",
                    "source": "internal_demo",
                }
            ],
            "degraded": False,
            "probability_components": [],
        },
        "insurance_risk": {
            "consistency_check": {
                "passed": True,
                "anomalies": [],
                "confidence_adjustment": "",
            },
            "risk_matrix": {
                "severity": {"score": 2, "reasoning": "Minor visible anomaly only."},
                "probability": {"score": 2, "reasoning": "No sign of rapid progression."},
                "consequence": {"score": 4, "reasoning": "ISS is a high-value critical asset."},
                "composite": 16,
            },
            "risk_tier": "LOW",
            "estimated_remaining_life_years": 5.0,
            "power_margin_percentage": 22.0,
            "annual_degradation_rate_pct": 1.2,
            "replacement_cost_usd": 150000000000.0,
            "depreciated_value_usd": 60000000000.0,
            "revenue_at_risk_annual_usd": 0.0,
            "total_loss_probability": 0.03,
            "underwriting_recommendation": "INSURABLE_STANDARD",
            "recommendation_rationale": "Observed anomaly is minor and consistent with managed LEO exposure.",
            "recommended_actions": [
                {
                    "priority": "LOW",
                    "timeframe": "Ongoing",
                    "action": "Continue nominal telemetry monitoring.",
                    "rationale": "No evidence of acute structural degradation.",
                }
            ],
            "worst_case_scenario": "Gradual panel efficiency loss without operational impact.",
            "summary": "ISS imagery shows a minor anomaly with low underwriting impact.",
            "degraded": False,
            "evidence_gaps": [],
            "report_completeness": "COMPLETE",
        },
    }


async def _collect_sse_events(response: httpx.Response) -> list[dict]:
    raw_events: list[dict] = []
    current: dict[str, list[str] | str] | None = None

    async for line in response.aiter_lines():
        if not line:
            if current:
                raw_events.append(current)
                current = None
            continue
        if line.startswith(":"):
            continue

        field, _, value = line.partition(":")
        value = value.lstrip()
        current = current or {}
        if field == "event":
            current["event"] = value
        elif field == "data":
            current.setdefault("data_lines", [])
            current["data_lines"].append(value)

    if current:
        raw_events.append(current)

    parsed_events = []
    for event in raw_events:
        data = "\n".join(event.get("data_lines", []))
        parsed_events.append(
            {
                "event": event.get("event", "message"),
                "data": json.loads(data) if data else None,
            }
        )
    return parsed_events


def _build_completed_analysis(sample_classification_result, sample_vision_result, sample_insurance_risk_result):
    now = datetime.now(timezone.utc)
    environment = {
        "orbital_regime": sample_classification_result["orbital_regime"],
        "altitude_km": 35786.0,
        "inclination_deg": 0.1,
        "debris_flux_density": "low",
        "collision_probability": "low",
        "radiation_dose_rate": "moderate",
        "thermal_cycling_range": "-120C to +120C",
        "atomic_oxygen_flux": "minimal",
        "stressors": [],
        "accelerating_factors": [],
        "mitigating_factors": ["operator station-keeping"],
        "data_sources": ["test"],
        "degraded": False,
    }
    failure_mode = {
        "failure_mode": "micrometeorite_impact",
        "mechanism": "single impact event",
        "root_cause_chain": ["external particle strike"],
        "progression_rate": "SLOW",
        "power_degradation_estimate_pct": 0.5,
        "remaining_life_revision_years": 0.1,
        "time_to_critical": "Not expected",
        "historical_precedents": [],
        "degraded": False,
        "probability_components": [],
    }
    return SimpleNamespace(
        id="analysis-e2e-record",
        status="completed",
        norad_id="25544",
        report_completeness="COMPLETE",
        created_at=now - timedelta(minutes=3),
        completed_at=now,
        classification_result=sample_classification_result,
        vision_result=sample_vision_result,
        environment_result=environment,
        failure_mode_result=failure_mode,
        insurance_risk_result=sample_insurance_risk_result,
        evidence_gaps=[],
    )


def _install_analysis_repository(monkeypatch, analyses):
    import db.base
    import db.repository

    class _FakeSessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakeAnalysisRepository:
        def __init__(self, session):
            self.session = session

        async def list_analyses(self, org_id=None, limit=20, offset=0):
            sliced = analyses[offset:offset + limit]
            return sliced, len(analyses)

    monkeypatch.setattr(db.base, "async_session_factory", lambda: _FakeSessionContext())
    monkeypatch.setattr(db.repository, "AnalysisRepository", _FakeAnalysisRepository)


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
async def test_health(client):
    resp = await client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "adk_available" in data
    assert isinstance(data["adk_available"], bool)
    assert "demo_mode" in data
    assert isinstance(data["demo_mode"], bool)


@pytest.mark.asyncio
async def test_analysis_pipeline_streams_full_agent_journey(client, monkeypatch, sample_image_bytes):
    payloads = _fake_pipeline_payloads()

    async def fake_run_satellite_pipeline(
        image_bytes: bytes,
        image_mime: str = "image/jpeg",
        norad_id: str | None = None,
        additional_context: str = "",
    ):
        assert image_bytes == sample_image_bytes
        assert image_mime == "image/jpeg"
        assert norad_id == "25544"

        analysis_id = "analysis-e2e"
        sequence = 0

        def emit(event: AgentEvent) -> dict:
            nonlocal sequence
            event.analysis_id = analysis_id
            event.sequence = sequence
            sequence += 1
            return format_sse_event(event)

        for agent in AGENT_ORDER:
            yield emit(AgentEvent.queued(agent))

        for agent in AGENT_ORDER:
            yield emit(AgentEvent.thinking(agent, f"{agent} is processing"))
            yield emit(AgentEvent.complete(agent, payloads[agent]))

        yield format_sse_done()

    monkeypatch.setattr(main, "run_satellite_pipeline", fake_run_satellite_pipeline)

    async with client.stream(
        "POST",
        "/api/analyze",
        files={"image": ("iss.jpg", sample_image_bytes, "image/jpeg")},
        data={"norad_id": "25544"},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = await _collect_sse_events(resp)

    agent_statuses = defaultdict(list)
    completed_payloads = {}

    for event in events:
        if event["event"] != "agent_event":
            continue
        data = event["data"]
        agent_statuses[data["agent"]].append(data["status"])
        if data["status"] == "complete":
            completed_payloads[data["agent"]] = data["payload"]

    assert set(agent_statuses) == set(AGENT_ORDER)
    for agent in AGENT_ORDER:
        assert agent_statuses[agent] == ["queued", "thinking", "complete"]

    classification = completed_payloads["orbital_classification"]
    assert classification["valid"] is True
    assert classification["satellite_type"] == "space_station"
    assert classification["orbital_regime"] == "LEO"

    insurance_risk = completed_payloads["insurance_risk"]
    assert insurance_risk["risk_tier"] == "LOW"
    assert insurance_risk["underwriting_recommendation"] == "INSURABLE_STANDARD"
    assert "risk_matrix" in insurance_risk

    assert any(
        event["event"] == "done" and event["data"] == {"status": "complete"}
        for event in events
    )


@pytest.mark.asyncio
async def test_demo_endpoint_list_and_stream(client):
    resp = await client.get("/api/demos")

    assert resp.status_code == 200
    data = resp.json()
    assert "demos" in data
    assert len(data["demos"]) == 3
    assert {"hubble_solar_array", "iss_solar_panel", "sentinel_1a"} == set(data["demos"])

    async with client.stream("POST", "/api/demo/hubble_solar_array") as stream_resp:
        assert stream_resp.status_code == 200
        assert stream_resp.headers["content-type"].startswith("text/event-stream")
        body = await stream_resp.aread()

    assert b"event:" in body


@pytest.mark.asyncio
async def test_analysis_persistence_list_shape(
    client,
    monkeypatch,
    sample_classification_result,
    sample_vision_result,
    sample_insurance_risk_result,
):
    analysis = _build_completed_analysis(
        sample_classification_result,
        sample_vision_result,
        sample_insurance_risk_result,
    )
    _install_analysis_repository(monkeypatch, [analysis])

    resp = await client.get("/api/analyses", params={"limit": 10, "offset": 0})

    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == {"items", "total", "limit", "offset"}
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert data["total"] >= 1
    assert isinstance(data["items"], list)
    assert any(item["id"] == analysis.id for item in data["items"])


@pytest.mark.asyncio
async def test_report_generation_returns_expected_sections(
    client,
    sample_classification_result,
    sample_vision_result,
    sample_insurance_risk_result,
):
    payload = {
        "classification": sample_classification_result,
        "vision": sample_vision_result,
        "environment": {
            "orbital_regime": "GEO",
            "altitude_km": 35786.0,
            "inclination_deg": 0.1,
        },
        "failure_mode": {
            "failure_mode": "micrometeorite_impact",
            "mechanism": "single impact event",
            "progression_rate": "SLOW",
        },
        "insurance_risk": sample_insurance_risk_result,
        "evidence_gaps": [],
        "report_completeness": "COMPLETE",
    }

    resp = await client.post("/api/reports/inline/generate-pdf", json=payload)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    html = resp.text
    assert "SATELLITE CONDITION REPORT" in html
    assert "Executive Summary" in html
    assert "Damage Assessment" in html
    assert "Insurance Risk Assessment" in html


@pytest.mark.asyncio
async def test_precedent_search_endpoints(client):
    resp = await client.get("/api/precedents")
    filtered_resp = await client.get("/api/precedents", params={"failure_mode": "deployment"})
    tags_resp = await client.get("/api/precedents/tags")

    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data
    assert data["total"] >= len(data["results"]) >= 1

    assert filtered_resp.status_code == 200
    filtered = filtered_resp.json()
    assert filtered["total"] >= 1
    assert filtered["results"]
    assert all("deployment" in item["failure_mode"].lower() for item in filtered["results"])

    assert tags_resp.status_code == 200
    tags = tags_resp.json()["tags"]
    assert tags["deployment"] >= 1


@pytest.mark.asyncio
async def test_portfolio_endpoints_return_satellite_list_and_risk_distribution(
    client,
    monkeypatch,
    sample_classification_result,
    sample_vision_result,
    sample_insurance_risk_result,
):
    analysis = _build_completed_analysis(
        sample_classification_result,
        sample_vision_result,
        sample_insurance_risk_result,
    )
    _install_analysis_repository(monkeypatch, [analysis])

    portfolio_resp = await client.get("/api/portfolio")
    summary_resp = await client.get("/api/portfolio/summary")

    assert portfolio_resp.status_code == 200
    portfolio = portfolio_resp.json()
    assert portfolio["total"] >= 1
    assert portfolio["satellites"]
    assert any(sat["norad_id"] == "25544" for sat in portfolio["satellites"])

    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_analyses"] >= 1
    assert summary["completed"] >= 1
    assert summary["risk_distribution"]["LOW"] >= 1


@pytest.mark.asyncio
async def test_webhook_crud(client, reset_webhooks):
    create_resp = await client.post(
        "/api/webhooks",
        json={
            "url": "https://example.com/orbital-inspect-webhook",
            "secret": "top-secret",
            "events": ["analysis.completed"],
        },
    )

    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["url"] == "https://example.com/orbital-inspect-webhook"
    assert created["events"] == ["analysis.completed"]
    webhook_id = created["id"]

    list_resp = await client.get("/api/webhooks")
    assert list_resp.status_code == 200
    listed = list_resp.json()["webhooks"]
    assert len(listed) == 1
    assert listed[0]["id"] == webhook_id

    delete_resp = await client.delete(f"/api/webhooks/{webhook_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"deleted": True}

    after_delete_resp = await client.get("/api/webhooks")
    assert after_delete_resp.status_code == 200
    assert after_delete_resp.json()["webhooks"] == []


@pytest.mark.asyncio
async def test_tle_history_analyzer_computes_orbital_health_score():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = [
        _tle_record(start + timedelta(days=index * 10), altitude, 0.0002 + index * 1e-5, 97.4 + index * 2e-4)
        for index, altitude in enumerate([550.0, 549.9, 549.8, 549.7, 549.6, 549.5])
    ]

    analysis = await analyze_tle_records("25544", records, days=90)

    assert analysis.sample_count == 6
    assert analysis.maneuver_count == 0
    assert analysis.orbit_decay_rate_km_per_day < 0
    assert analysis.overall_health_score >= 80
    assert analysis.health_rating in {"EXCELLENT", "GOOD"}


@pytest.mark.asyncio
async def test_enhanced_weather_service_parses_bz_data(monkeypatch):
    payload = [
        ["time_tag", "bx_gsm", "by_gsm", "bz_gsm", "lon_gsm", "lat_gsm", "bt"],
        ["2026-04-01 10:00:00.000", "1.0", "2.0", "", "0", "0", "5.0"],
        ["2026-04-01 10:01:00.000", "1.5", "2.5", "-7.5", "0", "0", "8.4"],
    ]

    bz_nt, bt_nt = await _extract_latest_bz(payload)
    assert bz_nt == pytest.approx(-7.5)
    assert bt_nt == pytest.approx(8.4)

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
        "https://services.swpc.noaa.gov/products/solar-wind/mag-7-day.json": payload,
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

    assert snapshot.bz_nt == pytest.approx(-7.5)
    assert snapshot.bt_nt == pytest.approx(8.4)
    assert snapshot.geoeffective is True
    assert snapshot.bz_orientation == "SOUTHWARD"
    assert snapshot.highest_alert_level == "WARNING"


@pytest.mark.asyncio
async def test_conjunction_service_computes_risk_scores():
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
    assert assessment.conjunction_risk_score >= 60
    assert assessment.most_threatening_objects[0]["counterparty_norad_id"] == "90001"


@pytest.mark.asyncio
async def test_report_generation_renders_provenance_sections(
    client,
    sample_classification_result,
    sample_vision_result,
    sample_insurance_risk_result,
):
    payload = {
        "classification": sample_classification_result,
        "vision": sample_vision_result,
        "environment": {"orbital_regime": "GEO"},
        "failure_mode": {
            "failure_mode": "solar_array_degradation",
            "mechanism": "cumulative MMOD",
        },
        "insurance_risk": {
            **sample_insurance_risk_result,
            "confidence_calibration": {
                "evidence_sufficiency": 0.72,
                "model_uncertainty": 0.21,
                "consensus_strength": 0.81,
                "calibrated_confidence": 0.76,
                "confidence_tier": "MODERATE",
                "basis": "Single-epoch imagery plus historical fleet priors.",
            },
            "loss_probability_derivation": {
                "components": [
                    {
                        "mechanism": "solar_array_failure",
                        "base_rate": 0.03,
                        "observed_evidence_factor": 1.4,
                        "adjusted_probability": 0.042,
                        "source": "fleet_historical_data",
                    }
                ],
                "aggregation_method": "independent_sum",
                "total_loss_probability": 0.042,
                "derivation_narrative": "Base rates adjusted using observed surface anomaly severity.",
            },
            "sensitivity_analysis": {
                "parameters": [
                    {
                        "name": "severity",
                        "baseline_value": 2,
                        "test_range_low": 1,
                        "test_range_high": 4,
                        "recommendation_at_low": "INSURABLE_STANDARD",
                        "recommendation_at_high": "FURTHER_INVESTIGATION",
                        "is_critical": True,
                    }
                ],
                "baseline_recommendation": "INSURABLE_STANDARD",
                "recommendation_robustness": "MARGINAL",
                "critical_thresholds": ["severity >= 4 -> FURTHER_INVESTIGATION"],
                "key_drivers": ["severity", "power_margin"],
            },
        },
        "evidence_gaps": [],
        "report_completeness": "COMPLETE",
    }

    resp = await client.post("/api/reports/inline/generate-pdf", json=payload)

    assert resp.status_code == 200
    html = resp.text
    assert "ASSESSMENT CONFIDENCE" in html
    assert "Loss Probability Derivation" in html
    assert "Sensitivity Analysis" in html
