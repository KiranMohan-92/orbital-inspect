"""Evidence Pack projection — the customer artifact path."""

from __future__ import annotations

import json
from pathlib import Path

from services.evidence_pack_service import (
    analysis_from_demo_cache,
    assert_pack_is_customer_safe,
    build_evidence_pack,
    write_pack_artifacts,
)
from services.pc_service import compute_pc_from_cdm_text

BACKEND = Path(__file__).resolve().parents[1]
SENTINEL_CACHE = BACKEND / "data" / "demo_cache" / "sentinel_1a.json"
SAMPLE_CDM = BACKEND / "inspection_core" / "spike" / "sample_cdm.txt"
LANDSAT = BACKEND / "data" / "reference_fixtures" / "landsat8_uneventful.json"


def test_public_data_pack_is_screening_only_with_gaps_and_no_insurable_conclusion():
    analysis = analysis_from_demo_cache(SENTINEL_CACHE)
    pack = build_evidence_pack(
        analysis=analysis,
        asset_name="SENTINEL-1A",
        norad_id="39634",
        generated_at="2026-08-12T00:00:00+00:00",
        software="test-sha",
    )
    assert_pack_is_customer_safe(pack)
    assert pack["decision_authority"] == "SCREENING_ONLY"
    assert pack["assessment_mode"] == "PUBLIC_SCREEN"
    assert pack["evidence_ledger"]
    assert any(row["status"] == "missing" for row in pack["evidence_ledger"])
    assert pack["next_human_action"] != "INSURABLE"
    assert "INSURABLE" not in pack["next_human_action"]
    assert "risk_matrix" not in pack
    assert "composite" not in pack
    assert pack["collision_probability"]["collision_probability"] is None
    assert pack["collision_probability"]["null_reason"]
    blob = json.dumps(pack)
    assert "SCREENING_ONLY" in blob


def test_pack_with_sample_cdm_uses_production_pc():
    analysis = json.loads(LANDSAT.read_text(encoding="utf-8"))
    cdm = SAMPLE_CDM.read_text(encoding="utf-8")
    expected = compute_pc_from_cdm_text(cdm)
    pack = build_evidence_pack(
        analysis=analysis,
        cdm_text=cdm,
        asset_name="ISS public conjunction fixture",
        norad_id="25544",
        generated_at="2026-08-12T00:00:00+00:00",
        software="test-sha",
    )
    assert pack["collision_probability"]["collision_probability"] == expected.collision_probability
    assert pack["collision_probability"]["collision_probability"] is not None
    assert pack["decision_authority"] == "SCREENING_ONLY"
    assert pack["next_human_action"] in {
        "continue_screen",
        "request_telemetry",
        "request_cdm",
        "escalate_specialist",
    }


def test_pack_non_psd_cdm_is_null_on_pack_path():
    analysis = json.loads(LANDSAT.read_text(encoding="utf-8"))
    mutated = SAMPLE_CDM.read_text(encoding="utf-8")
    mutated = mutated.replace("CR_R = 4.0e-04", "CR_R = 1.0e-04")
    mutated = mutated.replace("CT_T = 9.0e-03", "CT_T = 1.0e-04")
    mutated = mutated.replace("CT_R = 1.0e-04", "CT_R = 1.0e-02")
    pack = build_evidence_pack(analysis=analysis, cdm_text=mutated, asset_name="X", norad_id="1")
    assert pack["collision_probability"]["collision_probability"] is None
    assert pack["collision_probability"]["collision_probability"] != 0.0
    assert pack["collision_probability"]["null_reason"]


def test_two_packs_share_input_hash_and_authority(tmp_path):
    analysis = analysis_from_demo_cache(SENTINEL_CACHE)
    kwargs = dict(
        analysis=analysis,
        asset_name="SENTINEL-1A",
        norad_id="39634",
        generated_at="2026-08-12T00:00:00+00:00",
        software="test-sha",
    )
    a = build_evidence_pack(**kwargs)
    b = build_evidence_pack(**kwargs)
    assert a["reproducibility"]["input_hash"] == b["reproducibility"]["input_hash"]
    assert a["decision_authority"] == b["decision_authority"] == "SCREENING_ONLY"
    paths = write_pack_artifacts(a, tmp_path, "sentinel-test")
    written = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert written["reproducibility"]["input_hash"] == a["reproducibility"]["input_hash"]
    assert paths["pdf"].is_file() and paths["pdf"].stat().st_size > 100
    text = paths["pdf"].read_bytes()
    assert text.startswith(b"%PDF")
