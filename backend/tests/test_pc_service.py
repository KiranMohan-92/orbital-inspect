"""Production Pc path — drives services.pc_service, not a reimplementation."""

from __future__ import annotations

from pathlib import Path

from services.pc_service import compute_pc_from_cdm_text

SAMPLE_CDM = Path(__file__).resolve().parents[1] / "inspection_core" / "spike" / "sample_cdm.txt"


def test_good_fixture_cdm_yields_numeric_pc_via_production_service():
    text = SAMPLE_CDM.read_text(encoding="utf-8")
    first = compute_pc_from_cdm_text(text)
    second = compute_pc_from_cdm_text(text)

    assert first.collision_probability is not None
    assert first.null_reason is None
    assert 0.0 < first.collision_probability < 1.0
    assert first.covariance_quality == "usable_psd"
    assert first.method == "foster_akella_alfriend_2d"
    assert first.collision_probability == second.collision_probability


def test_missing_covariance_returns_null_not_zero():
    text = SAMPLE_CDM.read_text(encoding="utf-8")
    # Drop OBJECT2 CN_N so the parser treats that covariance as absent.
    stripped = text.replace("CN_N = 1.6e-02", "COMMENT CN_N stripped for test")
    result = compute_pc_from_cdm_text(stripped)

    assert result.collision_probability is None
    assert result.collision_probability != 0.0
    assert result.null_reason is not None
    assert "covariance" in result.null_reason.lower()
    assert result.covariance_quality == "missing"


def test_non_psd_covariance_returns_null_not_zero():
    text = SAMPLE_CDM.read_text(encoding="utf-8")
    # Off-diagonal dominant CR/CT block → negative eigenvalue.
    mutated = text.replace("CR_R = 4.0e-04", "CR_R = 1.0e-04")
    mutated = mutated.replace("CT_T = 9.0e-03", "CT_T = 1.0e-04")
    mutated = mutated.replace("CT_R = 1.0e-04", "CT_R = 1.0e-02")
    result = compute_pc_from_cdm_text(mutated)

    assert result.collision_probability is None
    assert result.collision_probability != 0.0
    assert result.null_reason is not None
    assert "positive-semidefinite" in result.null_reason.lower() or "psd" in result.null_reason.lower()
    assert result.covariance_quality == "non_psd"
