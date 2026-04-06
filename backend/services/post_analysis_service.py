"""
Shared post-analysis processing for decision and triage persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db.repository import (
    AnalysisRepository,
    AssetRepository,
    AuditLogRepository,
    EvidenceRepository,
)
from services.decision_policy_service import compute_triage, evaluate_decision_policy
from services.webhook_service import dispatch_registered_webhooks


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _seed_reference_sources(baseline_reference: dict[str, Any]) -> list[str]:
    raw = baseline_reference.get("reference_sources_json") or baseline_reference.get("reference_sources") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(item).strip() for item in raw if str(item).strip()]


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def _merge_dimensions(target: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "longitude_geo_deg",
        "perigee_km",
        "apogee_km",
        "inclination_deg",
        "period_min",
        "launch_mass_kg",
        "dry_mass_kg",
        "power_w",
        "expected_lifetime_yrs",
        "launch_date",
        "launch_vehicle",
        "launch_site",
        "country_code",
        "object_type",
        "site",
        "status",
    )
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            target.setdefault(key, value)
    return target


def _collect_reference_profile_inputs(
    analysis,
    evidence_pairs: list[tuple[Any, Any]],
) -> dict[str, Any]:
    baseline_reference = dict(getattr(analysis, "baseline_reference", {}) or {})
    capture_metadata = dict(getattr(analysis, "capture_metadata", {}) or {})
    classification = dict(getattr(analysis, "classification_result", {}) or {})

    operator_name = _first_non_empty(
        baseline_reference.get("operator_name"),
        capture_metadata.get("operator_name"),
        classification.get("operator"),
    )
    manufacturer = _first_non_empty(
        baseline_reference.get("manufacturer"),
        capture_metadata.get("manufacturer"),
    )
    mission_class = _first_non_empty(
        baseline_reference.get("mission_class"),
        baseline_reference.get("purpose"),
    )
    orbit_regime = _first_non_empty(
        baseline_reference.get("orbit_regime"),
        baseline_reference.get("orbit_class"),
    )
    reference_revision = _first_non_empty(
        baseline_reference.get("reference_revision"),
        baseline_reference.get("revision"),
    )
    dimensions_json = dict(
        baseline_reference.get("dimensions_json")
        or baseline_reference.get("dimensions")
        or {}
    )
    subsystem_baseline_json = dict(
        baseline_reference.get("subsystem_baseline_json")
        or baseline_reference.get("subsystem_baseline")
        or baseline_reference.get("subsystems")
        or {}
    )
    reference_sources = _seed_reference_sources(baseline_reference)
    if baseline_reference:
        reference_sources.append("analysis:baseline_reference")

    alias_candidates: dict[str, str | None] = {
        "operator_asset_id": _first_non_empty(
            baseline_reference.get("operator_asset_id"),
            capture_metadata.get("operator_asset_id"),
        ),
        "cospar": _first_non_empty(
            baseline_reference.get("cospar_id"),
            baseline_reference.get("international_designator"),
            capture_metadata.get("cospar_id"),
            capture_metadata.get("international_designator"),
        ),
        "satcat": _first_non_empty(
            baseline_reference.get("satcat_id"),
            capture_metadata.get("satcat_id"),
        ),
        "manufacturer_designation": _first_non_empty(
            baseline_reference.get("manufacturer_designation"),
            baseline_reference.get("platform"),
            capture_metadata.get("manufacturer_designation"),
        ),
    }
    last_verified_at = _coerce_datetime(baseline_reference.get("last_verified_at"))

    for _link, record in evidence_pairs:
        payload = dict(record.payload_json or {})
        source_ref = f"{record.provider or record.source_type}:{record.external_ref or record.id}"
        if record.evidence_role == "reference" or record.source_type == "reference_profile":
            reference_sources.append(source_ref)
            operator_name = operator_name or _first_non_empty(
                payload.get("operator_name"),
                payload.get("owner"),
            )
            manufacturer = manufacturer or _first_non_empty(payload.get("manufacturer"))
            mission_class = mission_class or _first_non_empty(
                payload.get("purpose"),
                payload.get("mission_class"),
                payload.get("object_type"),
            )
            orbit_regime = orbit_regime or _first_non_empty(
                payload.get("orbit_regime"),
                payload.get("orbit_class"),
            )
            alias_candidates["operator_asset_id"] = alias_candidates.get("operator_asset_id") or _first_non_empty(
                payload.get("operator_asset_id")
            )
            alias_candidates["cospar"] = alias_candidates.get("cospar") or _first_non_empty(
                payload.get("cospar_id"),
                payload.get("international_designator"),
            )
            alias_candidates["satcat"] = alias_candidates.get("satcat") or _first_non_empty(
                payload.get("satcat_id"),
                payload.get("norad_id"),
            )
            alias_candidates["manufacturer_designation"] = alias_candidates.get(
                "manufacturer_designation"
            ) or _first_non_empty(
                payload.get("manufacturer_designation"),
                payload.get("platform"),
            )
            _merge_dimensions(dimensions_json, payload)

            candidate_verified = _coerce_datetime(record.captured_at) or _coerce_datetime(record.ingested_at)
            if candidate_verified and (last_verified_at is None or candidate_verified > last_verified_at):
                last_verified_at = candidate_verified
        elif record.source_type == "celestrak":
            reference_sources.append(source_ref)
            orbit_regime = orbit_regime or _first_non_empty(
                payload.get("orbital_regime"),
                payload.get("orbit_regime"),
            )
            _merge_dimensions(dimensions_json, payload)

            candidate_verified = _coerce_datetime(record.captured_at) or _coerce_datetime(record.ingested_at)
            if candidate_verified and (last_verified_at is None or candidate_verified > last_verified_at):
                last_verified_at = candidate_verified

    normalized_alias_candidates = {
        alias_type: value.strip()
        for alias_type, value in alias_candidates.items()
        if isinstance(value, str) and value.strip()
    }
    reference_sources = _dedupe_strings(reference_sources)
    has_profile_data = any(
        [
            operator_name,
            manufacturer,
            mission_class,
            orbit_regime,
            reference_revision,
            dimensions_json,
            subsystem_baseline_json,
            reference_sources,
            normalized_alias_candidates,
        ]
    )
    return {
        "has_profile_data": has_profile_data,
        "operator_name": operator_name,
        "manufacturer": manufacturer,
        "mission_class": mission_class,
        "orbit_regime": orbit_regime,
        "reference_revision": reference_revision,
        "dimensions_json": dimensions_json,
        "subsystem_baseline_json": subsystem_baseline_json,
        "reference_sources_json": reference_sources,
        "last_verified_at": last_verified_at,
        "alias_candidates": normalized_alias_candidates,
    }


async def post_analysis_complete(
    *,
    analysis_id: str,
    session,
    actor_id: str = "system:post-analysis",
) -> None:
    analysis_repo = AnalysisRepository(session)
    asset_repo = AssetRepository(session)
    evidence_repo = EvidenceRepository(session)
    audit_logs = AuditLogRepository(session)

    analysis = await analysis_repo.get(analysis_id)
    if not analysis:
        return

    evidence_pairs = await evidence_repo.list_analysis_evidence(analysis_id=analysis.id)
    reference_inputs = _collect_reference_profile_inputs(analysis, evidence_pairs)

    classification = dict(getattr(analysis, "classification_result", {}) or {})
    baseline_reference = dict(getattr(analysis, "baseline_reference", {}) or {})
    capture_metadata = dict(getattr(analysis, "capture_metadata", {}) or {})
    external_asset_id = (
        baseline_reference.get("external_asset_id")
        or capture_metadata.get("external_asset_id")
        or classification.get("external_asset_id")
    )
    asset_name = (
        baseline_reference.get("asset_name")
        or capture_metadata.get("asset_name")
        or classification.get("name")
    )

    asset = await asset_repo.resolve_or_create(
        org_id=analysis.org_id,
        norad_id=analysis.norad_id,
        external_asset_id=external_asset_id,
        asset_type=getattr(analysis, "asset_type", "satellite"),
        name=asset_name,
        operator_name=reference_inputs.get("operator_name") or classification.get("operator"),
        alias_candidates=reference_inputs.get("alias_candidates"),
    )
    if getattr(analysis, "asset_id", None) != asset.id:
        await analysis_repo.update_fields(analysis_id, asset_id=asset.id)
        analysis = await analysis_repo.get(analysis_id)
        if not analysis:
            return

    subsystem = await asset_repo.resolve_or_create_subsystem(
        asset_id=asset.id,
        org_id=analysis.org_id,
        subsystem_key=getattr(analysis, "target_subsystem", None),
        display_name=getattr(analysis, "target_subsystem", None),
        subsystem_type=getattr(analysis, "target_subsystem", None),
    )
    if subsystem and getattr(analysis, "subsystem_id", None) != subsystem.id:
        await analysis_repo.update_fields(analysis_id, subsystem_id=subsystem.id)
        analysis = await analysis_repo.get(analysis_id)
        if not analysis:
            return

    await asset_repo.update_metadata(
        asset.id,
        norad_id=analysis.norad_id,
        external_asset_id=external_asset_id,
        name=asset.name or asset_name,
        operator_name=(
            asset.operator_name
            or reference_inputs.get("operator_name")
            or classification.get("operator")
        ),
    )
    await evidence_repo.reassign_analysis_evidence(
        analysis_id=analysis.id,
        asset_id=asset.id,
        subsystem_id=subsystem.id if subsystem else None,
    )
    if reference_inputs["has_profile_data"]:
        await evidence_repo.upsert_asset_reference_profile(
            asset_id=asset.id,
            org_id=analysis.org_id,
            operator_name=reference_inputs.get("operator_name"),
            manufacturer=reference_inputs.get("manufacturer"),
            mission_class=reference_inputs.get("mission_class"),
            orbit_regime=reference_inputs.get("orbit_regime"),
            reference_revision=reference_inputs.get("reference_revision"),
            dimensions_json=reference_inputs.get("dimensions_json"),
            subsystem_baseline_json=reference_inputs.get("subsystem_baseline_json"),
            reference_sources_json=reference_inputs.get("reference_sources_json"),
            last_verified_at=reference_inputs.get("last_verified_at"),
        )

    decision = evaluate_decision_policy(analysis)
    recurrence_count = await asset_repo.count_prior_attentionworthy_analyses(
        asset_id=asset.id,
        current_analysis_id=analysis.id,
    )
    triage_score, triage_band, triage_factors = compute_triage(
        analysis,
        decision_summary=decision.summary,
        decision_status=decision.status,
        recurrence_count=recurrence_count,
    )

    await analysis_repo.update_decision_state(
        analysis_id,
        decision_summary=decision.summary,
        decision_status=decision.status,
        decision_recommended_action=decision.summary.get("recommended_action"),
        decision_confidence=decision.summary.get("decision_confidence"),
        decision_urgency=decision.summary.get("urgency"),
        decision_blocked_reason=decision.summary.get("blocked_reason"),
        triage_score=triage_score,
        triage_band=triage_band,
        triage_factors=triage_factors,
        recurrence_count=recurrence_count,
    )
    await asset_repo.promote_current_analysis(asset_id=asset.id, analysis=analysis)
    await audit_logs.create(
        org_id=analysis.org_id,
        actor_id=actor_id,
        action="analysis.decision_evaluated",
        resource_type="analysis",
        resource_id=analysis_id,
        metadata_json={
            "asset_id": asset.id,
            "subsystem_id": subsystem.id if subsystem else None,
            "decision_status": decision.status,
            "recommended_action": decision.summary.get("recommended_action"),
            "triage_score": triage_score,
            "triage_band": triage_band,
        },
        analysis_id=analysis_id,
    )
    await dispatch_registered_webhooks(
        org_id=analysis.org_id,
        event_type="decision.created",
        payload={
            "analysis_id": analysis_id,
            "asset_id": asset.id,
            "decision_status": decision.status,
            "recommended_action": decision.summary.get("recommended_action"),
            "triage_score": triage_score,
            "triage_band": triage_band,
        },
    )


async def backfill_decisions(
    *,
    session,
    org_id: str | None = None,
    limit: int = 500,
) -> int:
    repo = AnalysisRepository(session)
    analyses = await repo.list_for_decision_backfill(org_id=org_id, limit=limit)
    processed = 0
    for analysis in analyses:
        await post_analysis_complete(
            analysis_id=analysis.id,
            session=session,
            actor_id="system:decision-backfill",
        )
        processed += 1
    return processed


def apply_review_action(
    *,
    current_status: str,
    action: str,
    override_action: str | None = None,
    actor_is_admin: bool = False,
) -> tuple[str, str | None]:
    if current_status not in {"pending_human_review", "approved_for_use", "blocked"}:
        raise ValueError(f"Decision review not allowed from {current_status}")

    if action == "approve":
        if current_status == "blocked":
            raise ValueError("Blocked decisions must be reset before approval")
        return "approved_for_use", None
    if action == "reset_review":
        return "pending_human_review", None
    if action == "block":
        return "blocked", None
    if action == "request_reimage":
        return "blocked", "reimage"
    if action == "override_action":
        if not actor_is_admin:
            raise ValueError("Only admins may override recommended action")
        if current_status == "blocked":
            raise ValueError("Blocked decisions must be reset before override")
        if not override_action:
            raise ValueError("override_action is required")
        return "approved_for_use", override_action
    raise ValueError(f"Unsupported review action: {action}")
