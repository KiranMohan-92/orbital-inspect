"""Persistence helpers for analysis evidence bundles."""

from __future__ import annotations

from datetime import datetime

from db.repository import EvidenceRepository
from models.evidence import EvidenceBundle, EvidenceItem, EvidenceSource


def _classify_item(item: EvidenceItem) -> tuple[str, str, str]:
    mapping = {
        EvidenceSource.IMAGERY: ("imagery", "runtime", "imagery"),
        EvidenceSource.TELEMETRY: ("operator_telemetry", "runtime", "telemetry"),
        EvidenceSource.TLE_HISTORY: ("celestrak", "runtime", "orbital_context"),
        EvidenceSource.CONJUNCTION_RISK: ("celestrak", "runtime", "conjunction_risk"),
        EvidenceSource.OPERATOR_NOTES: ("operator_notes", "runtime", "operator_notes"),
        EvidenceSource.MAINTENANCE_RECORDS: ("maintenance_records", "reference", "maintenance"),
        EvidenceSource.PRIOR_ANALYSIS: ("internal_prior_analysis", "runtime", "policy_context"),
        EvidenceSource.SPACE_WEATHER: ("noaa_swpc", "runtime", "environment"),
        EvidenceSource.DEBRIS_ENVIRONMENT: ("ordem", "runtime", "environment"),
        EvidenceSource.REFERENCE_PROFILE: ("reference_profile", "reference", "baseline"),
        EvidenceSource.RF_ACTIVITY: ("satnogs", "runtime", "rf_activity"),
    }
    return mapping[item.source]


def _coerce_timestamp(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def _external_ref_for_item(item: EvidenceItem, asset_id: str | None) -> str | None:
    metadata = item.metadata or {}
    explicit = metadata.get("external_ref")
    if explicit:
        return str(explicit)
    timestamp = item.timestamp or "unknown"
    if item.source == EvidenceSource.IMAGERY:
        return None
    return f"{item.source.value}:{asset_id or 'asset'}:{timestamp}"


async def persist_evidence_bundle(
    session,
    *,
    analysis_id: str,
    org_id: str | None,
    asset_id: str | None,
    subsystem_id: str | None,
    bundle: EvidenceBundle,
) -> int:
    repo = EvidenceRepository(session)
    linked = 0
    for item in bundle.items:
        source_type, evidence_role, used_for = _classify_item(item)
        metadata = item.metadata or {}
        record = await repo.upsert_record(
            org_id=org_id,
            asset_id=asset_id,
            subsystem_id=subsystem_id,
            source_type=source_type,
            evidence_role=evidence_role,
            provider=metadata.get("provider"),
            external_ref=_external_ref_for_item(item, asset_id),
            captured_at=_coerce_timestamp(item.timestamp),
            payload_json=item.payload or {},
            artifact_uri=metadata.get("storage_uri") or metadata.get("artifact_uri"),
            source_url=metadata.get("source_url"),
            license=metadata.get("license"),
            redistribution_policy=metadata.get("redistribution_policy"),
            confidence=item.confidence,
            geometry_metadata=metadata.get("geometry_metadata") or {},
            tags=metadata.get("tags") or [item.source.value],
        )
        await repo.link_analysis_evidence(
            analysis_id=analysis_id,
            evidence_id=record.id,
            used_for=used_for,
        )
        linked += 1
    return linked
