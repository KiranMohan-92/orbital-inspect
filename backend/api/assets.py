"""Asset and evidence APIs for operator-facing provenance and baseline context."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="", tags=["assets", "evidence"])


PUBLIC_SOURCES = {
    "celestrak",
    "tle_history",
    "conjunction_risk",
    "space_weather",
    "debris_environment",
    "reference_profile",
    "rf_activity",
    "noaa_swpc",
    "ordem",
    "satnogs",
}
OPERATOR_SUPPLIED_SOURCES = {
    "imagery",
    "operator_telemetry",
    "telemetry",
    "operator_notes",
    "maintenance_records",
}
INTERNAL_SOURCES = {
    "internal_prior_analysis",
    "prior_analysis",
}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _titleize(value: str | None) -> str:
    if not value:
        return "Unknown"
    return value.replace("_", " ").replace("-", " ").title()


def _confidence_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "unknown"
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.65:
        return "medium"
    return "low"


def _classify_source_domain(
    *,
    source_type: str | None,
    provider: str | None = None,
    evidence_role: str | None = None,
    tags: list[Any] | None = None,
) -> str:
    tag_values = {str(tag).lower() for tag in (tags or [])}
    source_lower = str(source_type or "").lower()
    provider_lower = str(provider or "").lower()

    if evidence_role == "offline_eval":
        return "offline_eval"
    if "partner" in tag_values or provider_lower.startswith("partner:"):
        return "partner"
    if source_lower in OPERATOR_SUPPLIED_SOURCES:
        return "operator_supplied"
    if source_lower in INTERNAL_SOURCES:
        return "internal"
    if source_lower in PUBLIC_SOURCES:
        return "public"
    return "unknown"


def _source_domain(record) -> str:
    return _classify_source_domain(
        source_type=record.source_type,
        provider=record.provider,
        evidence_role=record.evidence_role,
        tags=record.tags,
    )


def _source_label(record) -> str:
    provider = str(record.provider or "").strip()
    if provider:
        return provider
    return _titleize(record.source_type)


def _payload_highlights(record) -> list[str]:
    payload = dict(record.payload_json or {})
    source_type = str(record.source_type or "")
    highlights: list[str] = []

    if source_type == "imagery":
        image_count = payload.get("image_count")
        primary_filename = payload.get("primary_filename")
        if image_count is not None:
            highlights.append(f"{image_count} uploaded image(s)")
        if primary_filename:
            highlights.append(f"Primary file: {primary_filename}")
    elif source_type == "celestrak":
        if payload.get("orbital_regime"):
            highlights.append(f"Orbit: {payload['orbital_regime']}")
        if payload.get("overall_health_score") is not None:
            highlights.append(
                f"TLE health: {payload['overall_health_score']}/100"
            )
        elif payload.get("altitude_avg_km") is not None:
            highlights.append(f"Altitude: {payload['altitude_avg_km']} km")
    elif source_type == "reference_profile":
        if payload.get("operator_name"):
            highlights.append(f"Operator: {payload['operator_name']}")
        if payload.get("purpose"):
            highlights.append(f"Mission: {payload['purpose']}")
        if payload.get("manufacturer"):
            highlights.append(f"Manufacturer: {payload['manufacturer']}")
    elif source_type == "satnogs":
        if payload.get("observation_count") is not None:
            highlights.append(f"Observations: {payload['observation_count']}")
        if payload.get("distinct_stations") is not None:
            highlights.append(f"Stations: {payload['distinct_stations']}")
    elif source_type == "noaa_swpc":
        if payload.get("kp_index") is not None:
            highlights.append(f"Kp: {payload['kp_index']}")
        if payload.get("highest_alert_level"):
            highlights.append(f"Alert: {payload['highest_alert_level']}")
    elif source_type == "ordem":
        if payload.get("severity"):
            highlights.append(f"Debris: {payload['severity']}")
        if payload.get("altitude_km") is not None:
            highlights.append(f"Altitude: {payload['altitude_km']} km")
    elif source_type == "internal_prior_analysis":
        if payload.get("risk_tier"):
            highlights.append(f"Prior risk: {payload['risk_tier']}")
        if payload.get("underwriting_recommendation"):
            highlights.append(
                f"Recommendation: {payload['underwriting_recommendation']}"
            )

    if not highlights:
        for key in (
            "risk_tier",
            "underwriting_recommendation",
            "orbit_regime",
            "mission_class",
            "operator_name",
            "observation_count",
            "event_count",
        ):
            value = payload.get(key)
            if value not in (None, "", [], {}):
                highlights.append(f"{_titleize(key)}: {value}")
            if len(highlights) >= 3:
                break
    return highlights[:3]


def _serialize_evidence_item(record, *, used_for: str | None = None, link_id: str | None = None) -> dict[str, Any]:
    return {
        "evidence_id": record.id,
        "link_id": link_id,
        "used_for": used_for,
        "source_type": record.source_type,
        "evidence_role": record.evidence_role,
        "source_label": _source_label(record),
        "source_domain": _source_domain(record),
        "confidence": record.confidence,
        "confidence_bucket": _confidence_bucket(record.confidence),
        "provider": record.provider,
        "external_ref": record.external_ref,
        "captured_at": _iso(record.captured_at),
        "ingested_at": _iso(record.ingested_at),
        "source_url": record.source_url,
        "license": record.license,
        "redistribution_policy": record.redistribution_policy,
        "artifact_uri": record.artifact_uri,
        "geometry_metadata": record.geometry_metadata or {},
        "tags": record.tags or [],
        "highlights": _payload_highlights(record),
    }


def _serialize_reference_profile(profile) -> dict[str, Any] | None:
    if not profile:
        return None
    return {
        "operator_name": profile.operator_name,
        "manufacturer": profile.manufacturer,
        "mission_class": profile.mission_class,
        "orbit_regime": profile.orbit_regime,
        "reference_revision": profile.reference_revision,
        "dimensions_json": profile.dimensions_json or {},
        "subsystem_baseline_json": profile.subsystem_baseline_json or {},
        "reference_sources_json": profile.reference_sources_json or [],
        "last_verified_at": _iso(profile.last_verified_at),
        "updated_at": _iso(profile.updated_at),
    }


def _serialize_analysis_timeline_item(analysis) -> dict[str, Any]:
    insurance = dict(getattr(analysis, "insurance_risk_result", {}) or {})
    return {
        "analysis_id": analysis.id,
        "status": analysis.status,
        "inspection_epoch": getattr(analysis, "inspection_epoch", None),
        "target_subsystem": getattr(analysis, "target_subsystem", None),
        "subsystem_key": getattr(getattr(analysis, "subsystem", None), "subsystem_key", None),
        "risk_tier": insurance.get("risk_tier", "UNKNOWN"),
        "recommended_action": getattr(analysis, "decision_recommended_action", None),
        "decision_status": getattr(analysis, "decision_status", None),
        "triage_score": getattr(analysis, "triage_score", None),
        "triage_band": getattr(analysis, "triage_band", None),
        "evidence_completeness_pct": getattr(analysis, "evidence_completeness_pct", None),
        "report_completeness": getattr(analysis, "report_completeness", None),
        "degraded": getattr(analysis, "degraded", False),
        "created_at": _iso(getattr(analysis, "created_at", None)),
        "completed_at": _iso(getattr(analysis, "completed_at", None)),
    }


def _count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts = Counter(str(item.get(field) or "unknown") for item in items)
    return dict(sorted(counts.items()))


@router.get("/analyses/{analysis_id}/evidence")
async def get_analysis_evidence(
    analysis_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
    from db.base import async_session_factory
    from db.repository import AnalysisRepository, AssetRepository, EvidenceRepository

    async with async_session_factory() as session:
        analysis_repo = AnalysisRepository(session)
        evidence_repo = EvidenceRepository(session)
        asset_repo = AssetRepository(session)

        analysis = await analysis_repo.get(analysis_id, org_id=user.org_id if user else None)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        linked = await evidence_repo.list_analysis_evidence(analysis_id=analysis_id)
        items = [
            _serialize_evidence_item(record, used_for=link.used_for, link_id=link.id)
            for link, record in linked
        ]

        profile = None
        aliases: list[dict[str, Any]] = []
        if getattr(analysis, "asset_id", None):
            profile = await evidence_repo.get_asset_reference_profile(
                asset_id=analysis.asset_id,
                org_id=user.org_id if user else None,
            )
            aliases = [
                {
                    "alias_type": alias.alias_type,
                    "alias_value": alias.alias_value,
                    "is_primary": bool(alias.is_primary),
                }
                for alias in await asset_repo.list_aliases(analysis.asset_id)
            ]

        bundle_summary = getattr(analysis, "evidence_bundle_summary", {}) or {}
        return {
            "analysis_id": analysis.id,
            "asset": {
                "asset_id": getattr(analysis, "asset_id", None),
                "asset_name": getattr(getattr(analysis, "asset", None), "name", None),
                "asset_external_id": getattr(getattr(analysis, "asset", None), "external_asset_id", None),
                "asset_identity_source": getattr(getattr(analysis, "asset", None), "identity_source", None),
                "operator_name": getattr(getattr(analysis, "asset", None), "operator_name", None),
                "subsystem_id": getattr(analysis, "subsystem_id", None),
                "subsystem_key": getattr(getattr(analysis, "subsystem", None), "subsystem_key", None),
                "aliases": aliases,
            },
            "summary": {
                "evidence_completeness_pct": getattr(analysis, "evidence_completeness_pct", None),
                "report_completeness": getattr(analysis, "report_completeness", None),
                "evidence_gaps": getattr(analysis, "evidence_gaps", []) or [],
                "linked_evidence_count": bundle_summary.get("linked_evidence_count", len(items)),
                "sources_available": bundle_summary.get("sources_available", []),
                "evidence_quality": bundle_summary.get("evidence_quality", {}),
                "assessment_contract": bundle_summary.get("assessment_contract", {}),
                "prior_analyses_count": bundle_summary.get("prior_analyses_count", 0),
                "counts_by_role": _count_by(items, "evidence_role"),
                "counts_by_domain": _count_by(items, "source_domain"),
            },
            "reference_profile": _serialize_reference_profile(profile),
            "items": items,
        }


@router.get("/assets/{asset_id}")
async def get_asset_detail(
    asset_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
    from db.base import async_session_factory
    from db.repository import AssetRepository, EvidenceRepository

    async with async_session_factory() as session:
        asset_repo = AssetRepository(session)
        evidence_repo = EvidenceRepository(session)
        asset = await asset_repo.get_detail(asset_id, org_id=user.org_id if user else None)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        aliases = [
            {
                "alias_type": alias.alias_type,
                "alias_value": alias.alias_value,
                "is_primary": bool(alias.is_primary),
            }
            for alias in await asset_repo.list_aliases(asset.id)
        ]
        # Fetch only the recent slice for the response payload.
        recent_evidence_records = await evidence_repo.list_asset_evidence(
            asset_id=asset.id,
            org_id=user.org_id if user else None,
            limit=12,
        )
        recent_evidence = [_serialize_evidence_item(record) for record in recent_evidence_records]

        # Compute summary counts via DB-level aggregation (no full-table load).
        total_records, counts_by_role, counts_by_source_type, providers, latest_captured = (
            await evidence_repo.count_asset_evidence_summary(
                asset_id=asset.id,
                org_id=user.org_id if user else None,
            )
        )
        # Domain counts need source_type + provider because partner evidence is
        # identified by provider prefix rather than source_type alone.
        from sqlalchemy import func, or_, select
        from db.models import EvidenceRecord as ER

        domain_filters = [
            ER.asset_id == asset.id,
            or_(ER.evidence_role != "offline_eval", ER.evidence_role.is_(None)),
        ]
        if user and user.org_id:
            domain_filters.append(ER.org_id == user.org_id)

        domain_rows = await session.execute(
            select(ER.source_type, ER.provider, func.count())
            .where(*domain_filters)
            .group_by(ER.source_type, ER.provider)
        )
        counts_by_domain: dict[str, int] = {}
        for source_type, provider, count in domain_rows.all():
            domain = _classify_source_domain(
                source_type=source_type,
                provider=provider,
            )
            counts_by_domain[domain] = counts_by_domain.get(domain, 0) + count

        current_analysis = getattr(asset, "current_analysis", None)
        return {
            "asset": {
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
                "name": asset.name,
                "norad_id": asset.norad_id,
                "external_asset_id": asset.external_asset_id,
                "identity_source": asset.identity_source,
                "operator_name": asset.operator_name,
                "status": asset.status,
                "current_analysis_id": asset.current_analysis_id,
                "updated_at": _iso(asset.updated_at),
            },
            "aliases": aliases,
            "reference_profile": _serialize_reference_profile(getattr(asset, "reference_profile", None)),
            "evidence_summary": {
                "total_records": total_records,
                "counts_by_role": counts_by_role,
                "counts_by_domain": counts_by_domain,
                "providers": providers,
                "latest_captured_at": _iso(latest_captured),
            },
            "recent_evidence": recent_evidence,
            "current_analysis": _serialize_analysis_timeline_item(current_analysis) if current_analysis else None,
        }


@router.get("/assets/{asset_id}/timeline")
async def get_asset_timeline(
    asset_id: str,
    limit: int = 20,
    user: CurrentUser | None = Depends(get_current_user),
):
    from db.base import async_session_factory
    from db.repository import AssetRepository

    async with async_session_factory() as session:
        asset_repo = AssetRepository(session)
        asset = await asset_repo.get(asset_id, org_id=user.org_id if user else None)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        analyses = await asset_repo.list_analysis_timeline(
            asset_id=asset_id,
            org_id=user.org_id if user else None,
            limit=limit,
        )
        return {
            "asset_id": asset.id,
            "asset_name": asset.name,
            "analyses": [_serialize_analysis_timeline_item(analysis) for analysis in analyses],
        }
