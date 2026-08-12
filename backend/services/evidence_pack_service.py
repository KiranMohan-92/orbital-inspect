"""Customer Evidence Pack — public-data credit report projection.

This is the saleable artifact. It is a projection of the fail-closed
assessment contract plus optional computed Pc. It never emits a bind
recommendation, S×P×C composite as the conclusion, or dollar loss probability.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from services.assessment_mode_service import (
    UNDERWRITING_EVIDENCE_REQUIREMENTS,
    build_assessment_contract,
    normalize_assessment_mode,
)
from services.pc_service import PcComputation, compute_pc_from_cdm_text

log = logging.getLogger(__name__)

PACK_SCHEMA = "orbital-inspect.evidence_pack.v1"
ALLOWED_ACTIONS = {
    "continue_screen",
    "request_telemetry",
    "request_cdm",
    "escalate_specialist",
}
FORBIDDEN_CONCLUSION_KEYS = {
    "risk_matrix",
    "composite",
    "underwriting_recommendation",
    "replacement_cost_usd",
    "depreciated_value_usd",
    "revenue_at_risk_annual_usd",
    "total_loss_probability",
}


def software_sha() -> str:
    """Best-effort git SHA for the reproducibility stamp."""
    repo_root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        sha = result.stdout.strip()
        if sha:
            return sha
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def analysis_from_demo_cache(path: str | Path) -> dict[str, Any]:
    """Rebuild an analysis dict from a recorded SSE demo-cache file."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    stages: dict[str, dict[str, Any]] = {}
    for item in raw:
        if item.get("event") != "agent_event":
            continue
        data = item.get("data")
        if isinstance(data, str):
            data = json.loads(data)
        if not isinstance(data, dict) or data.get("status") != "complete":
            continue
        agent = data.get("agent")
        payload = data.get("payload") or {}
        if agent:
            stages[str(agent)] = payload
    return {
        "classification": stages.get("orbital_classification") or {},
        "vision": stages.get("satellite_vision") or {},
        "environment": stages.get("orbital_environment") or {},
        "failure_mode": stages.get("failure_mode") or {},
        "insurance_risk": stages.get("insurance_risk") or {},
    }


def _ledger_from_contract(contract: dict[str, Any]) -> list[dict[str, Any]]:
    present = contract.get("evidence_presence") or {}
    gap_by_id = {g["id"]: g for g in (contract.get("required_evidence_gaps") or [])}
    ledger = []
    for req in UNDERWRITING_EVIDENCE_REQUIREMENTS:
        rid = req["id"]
        if present.get(rid):
            ledger.append(
                {
                    "id": rid,
                    "label": req["label"],
                    "status": "present",
                    "description": req["description"],
                }
            )
        else:
            gap = gap_by_id.get(rid) or {}
            ledger.append(
                {
                    "id": rid,
                    "label": req["label"],
                    "status": gap.get("status") or "missing",
                    "description": gap.get("description") or req["description"],
                }
            )
    return ledger


def _next_action(
    ledger: list[dict[str, Any]],
    vision: dict[str, Any],
    pc: PcComputation | None,
) -> tuple[str, str]:
    missing = {row["id"] for row in ledger if row["status"] != "present"}
    if "covariance_cdm_quality" in missing or (pc is not None and pc.collision_probability is None):
        return (
            "request_cdm",
            "A usable Conjunction Data Message with positive-semidefinite "
            "covariance is required before collision probability can be computed.",
        )
    if "operator_telemetry" in missing:
        return (
            "request_telemetry",
            "Operator power, thermal, and attitude telemetry is required before "
            "any health or underwriting conclusion.",
        )
    damages = vision.get("damages") or []
    high = any(
        str(d.get("severity") or "").upper() in {"HIGH", "SEVERE", "CRITICAL"}
        for d in damages
        if isinstance(d, dict)
    )
    if high:
        return (
            "escalate_specialist",
            "Visible high-severity surface findings need a specialist review "
            "with calibrated imagery; this pack is not a bind decision.",
        )
    return (
        "continue_screen",
        "Public evidence is sufficient to keep this asset on a screening cadence. "
        "It is not sufficient to underwrite or bind.",
    )


def _input_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_evidence_pack(
    *,
    analysis: dict[str, Any],
    cdm_text: str | None = None,
    asset_name: str | None = None,
    norad_id: str | None = None,
    generated_at: str | None = None,
    software: str | None = None,
) -> dict[str, Any]:
    """Project a customer Evidence Pack from analysis + optional CDM."""
    classification = analysis.get("classification") or {}
    vision = analysis.get("vision") or {}
    environment = analysis.get("environment") or {}
    insurance = analysis.get("insurance_risk") or {}
    capture = dict(analysis.get("capture_metadata") or {})
    if cdm_text:
        capture["cdm"] = True

    contract = build_assessment_contract(
        assessment_mode=analysis.get("assessment_mode") or insurance.get("assessment_mode") or "PUBLIC_SCREEN",
        capture_metadata=capture,
        telemetry_summary=analysis.get("telemetry_summary") or {},
        baseline_reference=analysis.get("baseline_reference") or {},
        evidence_quality=analysis.get("evidence_quality") or {},
    )
    mode = normalize_assessment_mode(contract["assessment_mode"]).value
    authority = contract["decision_authority"]
    ledger = _ledger_from_contract(contract)

    pc: PcComputation | None = None
    if cdm_text:
        pc = compute_pc_from_cdm_text(cdm_text)
        if pc.covariance_quality == "usable_psd":
            for row in ledger:
                if row["id"] == "covariance_cdm_quality":
                    row["status"] = "present"
                    row["description"] = (
                        "Buyer-supplied CDM accepted; Pc computed with "
                        f"{pc.method}."
                    )
    elif not any(row["id"] == "covariance_cdm_quality" and row["status"] == "present" for row in ledger):
        pc = PcComputation(
            collision_probability=None,
            null_reason="Pc is NULL because no buyer-supplied CDM was provided. "
            "Public SOCRATES/CelesTrak columns are not a computed collision probability.",
            method="foster_akella_alfriend_2d",
            hard_body_radius_m=None,
            covariance_quality="absent",
            tca=None,
            miss_distance_m=None,
            primary_designator=None,
            secondary_designator=None,
        )

    action, action_rationale = _next_action(ledger, vision, pc)
    if action not in ALLOWED_ACTIONS:
        action = "escalate_specialist"

    blocked = list(contract.get("unsupported_claims_blocked") or [])
    if authority == "SCREENING_ONLY" and "underwriting_recommendation_without_private_evidence" not in blocked:
        blocked.append("underwriting_recommendation_without_private_evidence")

    stamp_time = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sha = software or software_sha()
    name = (
        asset_name
        or classification.get("operator") and f"{classification.get('operator')} {classification.get('satellite_type')}"
        or analysis.get("asset_name")
        or "Unnamed asset"
    )
    norad = norad_id or analysis.get("norad_id") or classification.get("norad_id")

    hash_inputs = {
        "schema": PACK_SCHEMA,
        "norad_id": norad,
        "asset_name": name,
        "assessment_mode": mode,
        "classification": classification,
        "vision": vision,
        "environment": environment,
        "cdm_sha256": hashlib.sha256((cdm_text or "").encode("utf-8")).hexdigest() if cdm_text else None,
        "ledger": ledger,
    }

    pack = {
        "schema": PACK_SCHEMA,
        "report_title": "Public Risk Screen",
        "assessment_mode": mode,
        "decision_authority": authority,
        "asset": {
            "name": name,
            "norad_id": norad,
            "satellite_type": classification.get("satellite_type"),
            "operator": classification.get("operator"),
            "orbital_regime": classification.get("orbital_regime") or environment.get("orbital_regime"),
        },
        "evidence_ledger": ledger,
        "blocked_claims": sorted(set(blocked)),
        "next_human_action": action,
        "next_human_action_rationale": action_rationale,
        "collision_probability": pc.to_dict() if pc is not None else {
            "collision_probability": None,
            "null_reason": "Pc is NULL because no CDM was supplied.",
            "method": "foster_akella_alfriend_2d",
            "covariance_quality": "absent",
        },
        "public_source_notes": environment.get("data_sources") or [],
        "visual_findings": [
            {
                "type": d.get("type"),
                "severity": d.get("severity"),
                "description": d.get("description"),
            }
            for d in (vision.get("damages") or [])
            if isinstance(d, dict)
        ],
        "summary": (
            "Public Risk Screen result; screening-only authority. "
            "This pack lists what public evidence shows, what is missing, "
            "and what a human should request next. It is not an underwriting "
            "or bind decision."
        ),
        "reproducibility": {
            "input_hash": _input_hash(hash_inputs),
            "software_sha": sha,
            "generated_at": stamp_time,
        },
    }

    for forbidden in FORBIDDEN_CONCLUSION_KEYS:
        pack.pop(forbidden, None)
    return pack


def render_pack_html(pack: dict[str, Any]) -> str:
    from jinja2 import Environment, FileSystemLoader

    template_dir = Path(__file__).resolve().parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    return env.get_template("evidence_pack.html").render(pack=pack)


def render_pack_pdf(pack: dict[str, Any], html: str | None = None) -> bytes:
    """Prefer WeasyPrint; fall back to a self-contained text PDF."""
    html = html if html is not None else render_pack_html(pack)
    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=html).write_pdf()
        if pdf_bytes:
            return pdf_bytes
    except Exception as exc:
        log.warning("WeasyPrint pack PDF unavailable (%s); using text PDF fallback", exc)
    return _simple_pack_pdf(pack)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _simple_pack_pdf(pack: dict[str, Any]) -> bytes:
    """Minimal single-page PDF so the buyer kit is attachable without Cairo."""
    pc = pack.get("collision_probability") or {}
    pc_line = (
        f"Pc = {pc.get('collision_probability')}"
        if pc.get("collision_probability") is not None
        else f"Pc = NULL — {pc.get('null_reason') or 'no CDM'}"
    )
    lines = [
        "ORBITAL INSPECT — PUBLIC RISK SCREEN",
        f"Asset: {pack.get('asset', {}).get('name')}  NORAD: {pack.get('asset', {}).get('norad_id')}",
        f"Decision authority: {pack.get('decision_authority')}",
        f"Assessment mode: {pack.get('assessment_mode')}",
        f"Next human action: {pack.get('next_human_action')}",
        pack.get("next_human_action_rationale") or "",
        pc_line,
        "Evidence ledger:",
    ]
    for row in pack.get("evidence_ledger") or []:
        lines.append(f"  [{row.get('status')}] {row.get('label')}")
    lines.append("Blocked claims: " + ", ".join(pack.get("blocked_claims") or []))
    stamp = pack.get("reproducibility") or {}
    lines.append(f"input_hash: {stamp.get('input_hash')}")
    lines.append(f"software_sha: {stamp.get('software_sha')}")
    lines.append(f"generated_at: {stamp.get('generated_at')}")
    lines.append("NOT AN UNDERWRITING OR BIND DECISION.")

    content_lines = ["BT", "/F1 10 Tf", "50 780 Td", "12 TL"]
    for line in lines:
        content_lines.append(f"({_pdf_escape(line[:110])}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        b"4 0 obj << /Length "
        + str(len(stream)).encode()
        + b" >> stream\n"
        + stream
        + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Courier >> endobj\n",
    ]
    header = b"%PDF-1.4\n"
    xref_offsets = [0]
    body = b""
    offset = len(header)
    for obj in objects:
        xref_offsets.append(offset)
        body += obj
        offset += len(obj)
    xref = [b"xref\n0 6\n0000000000 65535 f \n"]
    for off in xref_offsets[1:]:
        xref.append(f"{off:010d} 00000 n \n".encode())
    trailer = (
        b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(len(header) + len(body)).encode()
        + b"\n%%EOF\n"
    )
    return header + body + b"".join(xref) + trailer


def write_pack_artifacts(pack: dict[str, Any], out_dir: str | Path, stem: str) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{stem}.json"
    html_path = out / f"{stem}.html"
    pdf_path = out / f"{stem}.pdf"
    json_path.write_text(json.dumps(pack, indent=2, default=str) + "\n", encoding="utf-8")
    html = render_pack_html(pack)
    html_path.write_text(html, encoding="utf-8")
    pdf_path.write_bytes(render_pack_pdf(pack, html=html))
    return {"json": json_path, "html": html_path, "pdf": pdf_path}


def assert_pack_is_customer_safe(pack: dict[str, Any]) -> None:
    """Raise if a pack would present a bind/underwriting conclusion."""
    action = pack.get("next_human_action")
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"illegal next_human_action: {action}")
    if "INSURABLE" in str(action).upper():
        raise ValueError("pack next action must not be INSURABLE")
    blob = json.dumps(pack)
    if '"risk_matrix"' in blob or '"composite"' in blob:
        raise ValueError("customer pack must not present S×P×C / composite as a conclusion")
    if pack.get("decision_authority") != "SCREENING_ONLY" and pack.get("assessment_mode") == "PUBLIC_SCREEN":
        raise ValueError("public-data pack must be SCREENING_ONLY")
    if not pack.get("evidence_ledger"):
        raise ValueError("pack must list evidence gaps")
    stamp = pack.get("reproducibility") or {}
    if not stamp.get("input_hash") or not stamp.get("software_sha"):
        raise ValueError("pack must carry a reproducibility stamp")
