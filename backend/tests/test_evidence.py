"""Tests for evidence fusion models and service."""

import os
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

import pytest
from models.evidence import EvidenceBundle, EvidenceItem, EvidenceSource


def test_evidence_item_creation():
    item = EvidenceItem(
        source=EvidenceSource.TLE_HISTORY,
        data_type="application/json",
        description="TLE data",
        confidence=0.95,
        payload={"altitude_km": 408},
    )
    assert item.source == EvidenceSource.TLE_HISTORY
    assert item.confidence == 0.95
    assert item.payload["altitude_km"] == 408


def test_evidence_bundle_add_item():
    bundle = EvidenceBundle(satellite_id="25544")
    item = EvidenceItem(
        source=EvidenceSource.TLE_HISTORY,
        description="test",
    )
    bundle.add_item(item)
    assert bundle.total_items == 1
    assert "tle_history" in bundle.sources_available


def test_evidence_bundle_multiple_sources():
    bundle = EvidenceBundle(satellite_id="25544", satellite_name="ISS")
    bundle.add_item(EvidenceItem(source=EvidenceSource.TLE_HISTORY, description="TLE"))
    bundle.add_item(EvidenceItem(source=EvidenceSource.SPACE_WEATHER, description="Weather"))
    bundle.add_item(EvidenceItem(source=EvidenceSource.DEBRIS_ENVIRONMENT, description="Debris"))

    assert bundle.total_items == 3
    assert len(bundle.sources_available) == 3


def test_evidence_bundle_no_duplicate_sources():
    bundle = EvidenceBundle()
    bundle.add_item(EvidenceItem(source=EvidenceSource.TLE_HISTORY, description="1"))
    bundle.add_item(EvidenceItem(source=EvidenceSource.TLE_HISTORY, description="2"))
    assert bundle.sources_available.count("tle_history") == 1


def test_evidence_bundle_to_agent_context():
    bundle = EvidenceBundle(satellite_id="25544", satellite_name="ISS")
    bundle.add_item(EvidenceItem(
        source=EvidenceSource.TLE_HISTORY,
        description="Current TLE for NORAD 25544",
        payload={"altitude_avg_km": 408},
    ))

    context = bundle.to_agent_context()
    assert "ISS" in context
    assert "tle_history" in context
    assert "408" in context


def test_evidence_source_enum_values():
    assert EvidenceSource.IMAGERY.value == "imagery"
    assert EvidenceSource.TELEMETRY.value == "telemetry"
    assert EvidenceSource.PRIOR_ANALYSIS.value == "prior_analysis"
    assert EvidenceSource.CONJUNCTION_RISK.value == "conjunction_risk"
    assert len(EvidenceSource) == 9


def test_evidence_bundle_prior_risk_tiers():
    bundle = EvidenceBundle()
    bundle.prior_analyses_count = 3
    bundle.prior_risk_tiers = ["LOW", "MEDIUM", "MEDIUM-HIGH"]

    context = bundle.to_agent_context()
    assert "LOW → MEDIUM → MEDIUM-HIGH" in context


def test_evidence_item_defaults():
    item = EvidenceItem(source=EvidenceSource.IMAGERY)
    assert item.confidence == 1.0
    assert item.payload == {}
    assert item.metadata == {}
    assert item.data_type == ""
